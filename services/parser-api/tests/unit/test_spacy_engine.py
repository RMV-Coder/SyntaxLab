"""spaCy -> SyntaxLab normalization and model installation, with no models or network."""

from __future__ import annotations

import hashlib
import urllib.error
import zipfile
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("spacy")

import spacy
from spacy.tokens import Doc

from syntaxlab_api.analysis.validate import validate_sentence
from syntaxlab_api.engines import spacy_engine
from syntaxlab_api.engines.base import EngineConfigError, EngineContext, EngineError
from syntaxlab_api.engines.spacy_engine import (
    SpacyEngine,
    collapse_whitespace,
    fetch,
    find_pipeline_dir,
    keep_hyphenated_words,
    mark_sentence_boundaries,
    normalize_span,
    safe_extract,
    verify_sha256,
)
from syntaxlab_api.schemas.analysis import Capability, StructureKind

OPTIONS: dict[str, Any] = {
    "model": "tl_test",
    "version": "1.0",
    "wheel_url": "https://example.test/model.whl",
    "wheel_sha256": "0" * 64,
    "components": ["trainable_lemmatizer", "morphologizer", "parser"],
    "shared_components": ["tok2vec"],
}


def engine(tmp_path: Path | None = None, **overrides: Any) -> SpacyEngine:
    return SpacyEngine(
        EngineContext(
            language="tl",
            options={**OPTIONS, **overrides},
            schemes={Capability.DEPENDENCY: "ud-2"},
            models_dir=tmp_path,
        )
    )


def parsed_doc() -> Doc:
    """ "Kumain ang bata." with an analysis, as a pipeline would leave it."""
    nlp = spacy.blank("xx")
    return Doc(
        nlp.vocab,
        words=["Kumain", "ang", "bata", "."],
        spaces=[True, True, False, False],
        pos=["VERB", "DET", "NOUN", "PUNCT"],
        lemmas=["kain", "ang", "bata", "."],
        morphs=["Aspect=Perf|Voice=Act", "Case=Nom", "", ""],
        heads=[0, 2, 0, 0],
        deps=["ROOT", "det", "nsubj", "punct"],
        sent_starts=[True, False, False, False],
    )


class TestOptions:
    def test_capabilities_follow_components_without_loading(self) -> None:
        caps = engine().capabilities()
        assert set(caps) == {
            Capability.TOKENIZATION,
            Capability.POS,
            Capability.MORPHOLOGY,
            Capability.LEMMA,
            Capability.DEPENDENCY,
        }
        assert caps[Capability.DEPENDENCY] == "spacy/tl_test/1.0/parser"

    def test_never_claims_constituency(self) -> None:
        assert Capability.CONSTITUENCY not in engine().capabilities()

    def test_without_parser_there_is_no_dependency_capability(self) -> None:
        caps = engine(components=["morphologizer"]).capabilities()
        assert Capability.DEPENDENCY not in caps
        assert Capability.LEMMA not in caps

    def test_model_id(self) -> None:
        assert engine().model_id == "spacy:tl_test:1.0"

    @pytest.mark.parametrize("missing", ["model", "version", "wheel_url", "wheel_sha256"])
    def test_required_options(self, missing: str) -> None:
        options = {k: v for k, v in OPTIONS.items() if k != missing}
        with pytest.raises(EngineConfigError, match=missing):
            SpacyEngine(EngineContext(language="tl", options=options))

    @pytest.mark.parametrize(
        ("overrides", "message"),
        [
            ({"components": []}, "at least one"),
            ({"components": "parser"}, "list of strings"),
            ({"components": ["ner"]}, "unsupported"),
            ({"shared_components": "tok2vec"}, "list of strings"),
            ({"keep_hyphenated_words": "yes"}, "true or false"),
            ({"split_sentences": 1}, "true or false"),
            ({"abbreviations": "Dr."}, "list of strings"),
            ({"surprise": True}, "unknown"),
        ],
    )
    def test_rejects_invalid_options(self, overrides: dict[str, Any], message: str) -> None:
        with pytest.raises(EngineConfigError, match=message):
            engine(**overrides)

    def test_analyze_before_load_is_an_error(self) -> None:
        with pytest.raises(EngineError, match="not loaded"):
            engine().analyze("Kumain.", frozenset({StructureKind.DEPENDENCY}))

    def test_load_without_install_says_how_to_fix_it(self, tmp_path: Path) -> None:
        with pytest.raises(EngineError, match="download-models"):
            engine(tmp_path).load()


class TestNormalize:
    def test_translates_root_and_copies_everything_else(self) -> None:
        doc = parsed_doc()
        text = doc.text
        _, offsets = collapse_whitespace(text)
        [span] = list(doc.sents)
        sentence = normalize_span(span, text, offsets, dependency_scheme="ud-2")
        validate_sentence(sentence)
        assert [t.form for t in sentence.tokens] == ["Kumain", "ang", "bata", "."]
        assert sentence.tokens[0].lemma == "kain"
        assert sentence.tokens[0].upos == "VERB"
        assert sentence.tokens[0].feats == {"Aspect": "Perf", "Voice": "Act"}
        assert sentence.tokens[3].feats == {}
        assert sentence.dependency is not None
        arcs = [(a.dependent, a.head, a.relation) for a in sentence.dependency.arcs]
        assert arcs == [(1, 0, "root"), (2, 3, "det"), (3, 1, "nsubj"), (4, 1, "punct")]

    def test_no_fabricated_xpos_when_no_tagger_ran(self) -> None:
        doc = parsed_doc()
        _, offsets = collapse_whitespace(doc.text)
        [span] = list(doc.sents)
        sentence = normalize_span(span, doc.text, offsets, dependency_scheme="ud-2")
        assert all(t.xpos is None for t in sentence.tokens)

    def test_dependency_only_when_requested(self) -> None:
        doc = parsed_doc()
        _, offsets = collapse_whitespace(doc.text)
        [span] = list(doc.sents)
        assert normalize_span(span, doc.text, offsets, dependency_scheme=None).dependency is None

    def test_offsets_refer_to_the_submitted_text(self) -> None:
        submitted = "Kumain  ang\n bata."
        collapsed, offsets = collapse_whitespace(submitted)
        assert collapsed == "Kumain ang bata."
        doc = parsed_doc()
        [span] = list(doc.sents)
        sentence = normalize_span(span, submitted, offsets, dependency_scheme="ud-2")
        for token in sentence.tokens:
            assert submitted[token.start_char : token.end_char] == token.form
        assert sentence.text == submitted

    def test_missing_labels_are_an_error_not_a_guess(self) -> None:
        nlp = spacy.blank("xx")
        doc = Doc(nlp.vocab, words=["a"], sent_starts=[True])
        [span] = list(doc.sents)
        with pytest.raises(EngineError, match="no labels"):
            normalize_span(span, "a", [0], dependency_scheme="ud-2")

    def test_head_outside_the_sentence_is_an_error(self) -> None:
        # spaCy keeps trees within a sentence, so this needs a hand-made span.
        outside = SimpleNamespace(i=0)
        word = SimpleNamespace(
            i=1,
            text="b",
            idx=2,
            lemma_="b",
            pos_="X",
            tag_="",
            morph=SimpleNamespace(to_dict=dict),
            dep_="dep",
            head=outside,
        )
        with pytest.raises(EngineError, match="another sentence"):
            normalize_span([word], "a b", [0, 1, 2], dependency_scheme="ud-2")


class TestCollapseWhitespace:
    @pytest.mark.parametrize(
        ("text", "collapsed", "offsets"),
        [
            ("ab", "ab", [0, 1]),
            ("a b", "a b", [0, 1, 2]),
            ("a  b", "a b", [0, 1, 3]),
            ("a\t\n b", "a b", [0, 1, 4]),
            ("a\u00a0b", "a b", [0, 1, 2]),
            ("", "", []),
        ],
    )
    def test_maps_every_character_back(self, text: str, collapsed: str, offsets: list[int]) -> None:
        assert collapse_whitespace(text) == (collapsed, offsets)


class TestSentenceBoundaries:
    @staticmethod
    def sentences(text: str, abbreviations: frozenset[str] = frozenset()) -> list[str]:
        doc = spacy.blank("tl").make_doc(text)
        mark_sentence_boundaries(doc, abbreviations)
        return [span.text for span in doc.sents]

    def test_one_sentence(self) -> None:
        assert self.sentences("Gumising ang bata.") == ["Gumising ang bata."]

    def test_splits_at_final_punctuation(self) -> None:
        assert self.sentences("Gumising ang bata. Natulog ang nanay! Sino ka?") == [
            "Gumising ang bata.",
            "Natulog ang nanay!",
            "Sino ka?",
        ]

    def test_no_final_punctuation(self) -> None:
        assert self.sentences("Gumising ang bata") == ["Gumising ang bata"]

    def test_closing_punctuation_stays_with_its_sentence(self) -> None:
        assert self.sentences('"Gumising ka." Natulog siya.') == [
            '"Gumising ka."',
            "Natulog siya.",
        ]

    def test_repeated_punctuation_is_one_boundary(self) -> None:
        assert self.sentences("Talaga?! Oo.") == ["Talaga?!", "Oo."]

    def test_abbreviation_period_does_not_end_a_sentence(self) -> None:
        text = "Dumating si Dr. Santos kahapon."
        assert len(self.sentences(text)) == 2  # without the list
        assert self.sentences(text, frozenset({"Dr"})) == [text]

    def test_abbreviations_only_excuse_periods(self) -> None:
        assert len(self.sentences("Dr? Oo.", frozenset({"Dr"}))) == 2


class TestHyphenRule:
    def test_keeps_hyphenated_words_whole_and_nothing_else_changes(self) -> None:
        nlp = spacy.blank("tl")
        assert [t.text for t in nlp("nag-aral")] == ["nag", "-", "aral"]
        keep_hyphenated_words(nlp, spacy)
        assert [t.text for t in nlp("nag-aral")] == ["nag-aral"]
        # Hyphens between digits, and other punctuation, are not affected.
        assert [t.text for t in nlp("3-4 aso, pusa.")] == ["3", "-", "4", "aso", ",", "pusa", "."]
        assert [t.text for t in nlp('"aso"')] == ['"', "aso", '"']

    def test_fails_loudly_if_spacy_changes_the_rule(self) -> None:
        nlp = SimpleNamespace(Defaults=SimpleNamespace(infixes=("something else",)))
        with pytest.raises(EngineError, match="not found"):
            keep_hyphenated_words(nlp, spacy)


class TestInstall:
    def test_verify_sha256(self, tmp_path: Path) -> None:
        path = tmp_path / "file"
        path.write_bytes(b"model")
        verify_sha256(path, hashlib.sha256(b"model").hexdigest())
        with pytest.raises(EngineError, match="checksum mismatch"):
            verify_sha256(path, "0" * 64)

    def test_safe_extract_refuses_paths_outside_the_target(self, tmp_path: Path) -> None:
        wheel = tmp_path / "evil.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("../../outside.txt", "x")
        with pytest.raises(EngineError, match="unsafe path"):
            safe_extract(wheel, tmp_path / "target")
        assert not (tmp_path.parent / "outside.txt").exists()

    def test_find_pipeline_dir(self, tmp_path: Path) -> None:
        assert find_pipeline_dir(tmp_path / "absent") is None
        assert find_pipeline_dir(tmp_path) is None
        nested = tmp_path / "pkg" / "pkg-1.0"
        nested.mkdir(parents=True)
        (nested / "config.cfg").write_text("")
        assert find_pipeline_dir(tmp_path) == nested

    def test_download_verifies_then_installs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("tl_test/tl_test-1.0/config.cfg", "")
        payload = buffer.getvalue()
        monkeypatch.setattr(spacy_engine.urllib.request, "urlopen", _server([_ok(payload)]))
        target = engine(tmp_path, wheel_sha256=hashlib.sha256(payload).hexdigest())
        target.download()
        assert find_pipeline_dir(tmp_path / "spacy" / "tl_test-1.0") is not None
        assert not list((tmp_path / "spacy").glob("*.whl"))

    def test_download_with_wrong_hash_installs_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(spacy_engine.urllib.request, "urlopen", _server([_ok(b"tampered")]))
        with pytest.raises(EngineError, match="checksum mismatch"):
            engine(tmp_path).download()
        assert not (tmp_path / "spacy" / "tl_test-1.0").exists()

    def test_download_without_a_pipeline_installs_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("readme.txt", "no pipeline here")
        payload = buffer.getvalue()
        monkeypatch.setattr(spacy_engine.urllib.request, "urlopen", _server([_ok(payload)]))
        with pytest.raises(EngineError, match="no spaCy pipeline"):
            engine(tmp_path, wheel_sha256=hashlib.sha256(payload).hexdigest()).download()

    def test_download_skips_when_already_installed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        installed = tmp_path / "spacy" / "tl_test-1.0" / "tl_test"
        installed.mkdir(parents=True)
        (installed / "config.cfg").write_text("")

        def fail(*_: Any, **__: Any) -> None:
            raise AssertionError("must not download")

        monkeypatch.setattr(spacy_engine.urllib.request, "urlopen", fail)
        engine(tmp_path).download()


class _Response(BytesIO):
    def __init__(self, data: bytes, status: int = 200) -> None:
        super().__init__(data)
        self.status = status

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _ok(data: bytes, status: int = 200) -> _Response:
    return _Response(data, status)


def _server(responses: list[Any]) -> Any:
    """A fake ``urlopen`` serving one prepared response (or raising one error) per request."""
    queue: Iterator[Any] = iter(responses)
    requests: list[Any] = []

    def urlopen(request: Any, timeout: float) -> Any:
        requests.append(request)
        response = next(queue)
        if isinstance(response, Exception):
            raise response
        return response

    urlopen.requests = requests  # type: ignore[attr-defined]
    return urlopen


class _Stalls(_Response):
    """Delivers its data, then a read fails as a dropped connection would."""

    def read(self, size: int | None = -1) -> bytes:
        data = super().read(size)
        if not data:
            raise TimeoutError("connection stalled")
        return data


class TestFetch:
    def test_downloads_a_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(spacy_engine.urllib.request, "urlopen", _server([_ok(b"model")]))
        destination = tmp_path / "file"
        fetch("https://example.test/file", destination)
        assert destination.read_bytes() == b"model"

    def test_resumes_after_a_stall(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        server = _server([_Stalls(b"mod"), _ok(b"el", status=206)])
        monkeypatch.setattr(spacy_engine.urllib.request, "urlopen", server)
        destination = tmp_path / "file"
        fetch("https://example.test/file", destination)
        assert destination.read_bytes() == b"model"
        assert server.requests[1].get_header("Range") == "bytes=3-"

    def test_restarts_when_the_server_ignores_the_range(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        server = _server([_Stalls(b"mod"), _ok(b"model", status=200)])
        monkeypatch.setattr(spacy_engine.urllib.request, "urlopen", server)
        destination = tmp_path / "file"
        fetch("https://example.test/file", destination)
        assert destination.read_bytes() == b"model"

    def test_range_past_the_end_means_complete(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        error = urllib.error.HTTPError("u", 416, "range", None, None)  # type: ignore[arg-type]
        monkeypatch.setattr(spacy_engine.urllib.request, "urlopen", _server([error]))
        destination = tmp_path / "file"
        destination.write_bytes(b"model")
        fetch("https://example.test/file", destination)
        assert destination.read_bytes() == b"model"

    def test_gives_up_after_repeated_failures(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        errors = [urllib.error.URLError("down") for _ in range(spacy_engine._DOWNLOAD_ATTEMPTS)]
        monkeypatch.setattr(spacy_engine.urllib.request, "urlopen", _server(errors))
        with pytest.raises(EngineError, match="could not download"):
            fetch("https://example.test/file", tmp_path / "file")

    def test_a_trickle_counts_as_a_stall(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        clock = iter(range(0, 10_000, 100))
        monkeypatch.setattr(spacy_engine.time, "monotonic", lambda: next(clock))
        source = BytesIO(b"x" * 10)
        with pytest.raises(TimeoutError, match="bytes in"), (tmp_path / "file").open("wb") as out:
            spacy_engine._copy_watching_for_stalls(_OneByte(source), out)


class _OneByte:
    def __init__(self, source: BytesIO) -> None:
        self.source = source

    def read(self, _: int) -> bytes:
        return self.source.read(1)
