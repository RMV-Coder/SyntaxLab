"""Generic spaCy engine (https://spacy.io/).

One class serves every language with a spaCy pipeline that follows Universal Dependencies; the
language entry in ``config/languages.yaml`` selects the model. Supported ``engine_options``:

    model:        pipeline package name, e.g. "tl_calamancy_lg" (required)
    version:      pipeline version, e.g. "0.2.0" (required)
    wheel_url:    where to download the pipeline's wheel (required)
    wheel_sha256: expected SHA-256 of that wheel (required)
    components:   pipeline components to run (required). Capabilities are derived from this
                  list; everything else in the pipeline is excluded unless a listed component
                  needs it (``shared_components``).
    shared_components: components that only feed others, e.g. "tok2vec" (default: none)
    keep_hyphenated_words: remove spaCy's letter-hyphen-letter tokenizer rule, for treebanks
                  that keep such words whole (default: false). See docs/research.
    split_sentences: find sentence boundaries by punctuation before parsing, for pipelines
                  whose parser does not learn them (default: false). See docs/research.
    abbreviations: words whose following period does not end a sentence, written without the
                  period, for split_sentences (default: none). Tokenization is not affected.

Wheels are not installed. Model packages can declare dependencies that have nothing to do with
running them (calamanCy's declare an obsolete ``spacy-transformers``), so ``download()`` verifies
the wheel's hash and unpacks the pipeline data under ``models_dir``, and ``load()`` reads it from
there against SyntaxLab's own pinned spaCy.

Runs of whitespace are collapsed before analysis: spaCy would otherwise make them tokens, and the
parser would attach them like words. Character offsets still refer to the original text.

``spacy`` is imported lazily so the API can describe languages (and run its test-suite) without
it installed.
"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.request
import warnings
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

from syntaxlab_api.engines.base import Engine, EngineConfigError, EngineContext, EngineError
from syntaxlab_api.schemas.analysis import (
    Capability,
    DependencyAnalysis,
    DependencyArc,
    SentenceAnalysis,
    StructureKind,
    Token,
)

# Which SyntaxLab capabilities each spaCy component provides.
_COMPONENT_CAPABILITIES: Mapping[str, tuple[Capability, ...]] = {
    "tagger": (),  # language-specific tags (Token.xpos) only
    "morphologizer": (Capability.POS, Capability.MORPHOLOGY),
    "lemmatizer": (Capability.LEMMA,),
    "trainable_lemmatizer": (Capability.LEMMA,),
    "parser": (Capability.DEPENDENCY,),
}
_DOWNLOAD_CHUNK = 1024 * 1024
_DOWNLOAD_ATTEMPTS = 5
# Model hosts can stall part-way without closing the connection: give up on an attempt, and
# resume, when less than this many bytes arrive in a window.
_STALL_WINDOW_S = 60.0
_STALL_MIN_BYTES = 1024 * 1024
_WHITESPACE = re.compile(r"\s+")
_SENTENCE_FINAL = frozenset({".", "!", "?"})

logger = logging.getLogger(__name__)


class SpacyEngine(Engine):
    name: ClassVar[str] = "spacy"

    def __init__(self, context: EngineContext) -> None:
        super().__init__(context)
        opts = dict(context.options)
        self.model = _required_str(opts, "model")
        self.version = _required_str(opts, "version")
        self.wheel_url = _required_str(opts, "wheel_url")
        self.wheel_sha256 = _required_str(opts, "wheel_sha256").lower()
        self.components = _string_tuple(opts.pop("components", None), "components")
        if not self.components:
            raise EngineConfigError("spacy 'components' must list at least one component")
        unknown = set(self.components) - set(_COMPONENT_CAPABILITIES)
        if unknown:
            raise EngineConfigError(f"unsupported spacy components: {sorted(unknown)}")
        self.shared_components = _string_tuple(
            opts.pop("shared_components", []), "shared_components"
        )
        keep_hyphenated = opts.pop("keep_hyphenated_words", False)
        if not isinstance(keep_hyphenated, bool):
            raise EngineConfigError("spacy 'keep_hyphenated_words' must be true or false")
        self.keep_hyphenated_words: bool = keep_hyphenated
        split_sentences = opts.pop("split_sentences", False)
        if not isinstance(split_sentences, bool):
            raise EngineConfigError("spacy 'split_sentences' must be true or false")
        self.split_sentences: bool = split_sentences
        self.abbreviations = frozenset(
            _string_tuple(opts.pop("abbreviations", []), "abbreviations")
        )
        if opts:
            raise EngineConfigError(f"unknown spacy engine options: {sorted(opts)}")
        self._nlp: Any = None

    # ------------------------------------------------------------------ metadata

    def capabilities(self) -> Mapping[Capability, str]:
        caps: dict[Capability, str] = {
            Capability.TOKENIZATION: f"spacy/{self.model}/{self.version}/tokenizer"
        }
        for component in self.components:
            for capability in _COMPONENT_CAPABILITIES[component]:
                caps[capability] = f"spacy/{self.model}/{self.version}/{component}"
        return caps

    @property
    def engine_version(self) -> str | None:
        try:
            from spacy import about
        except ImportError:
            return None
        return str(about.__version__)

    @property
    def model_id(self) -> str:
        return f"spacy:{self.model}:{self.version}"

    # ------------------------------------------------------------------ lifecycle

    def _install_dir(self) -> Path:
        if self.context.models_dir is None:
            raise EngineConfigError("the spacy engine needs a models directory")
        return self.context.models_dir / "spacy" / f"{self.model}-{self.version}"

    def download(self) -> None:
        target = self._install_dir()
        if find_pipeline_dir(target) is not None:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=target.parent) as scratch:
            wheel = Path(scratch) / "model.whl"
            fetch(self.wheel_url, wheel)
            verify_sha256(wheel, self.wheel_sha256)
            unpacked = Path(scratch) / "unpacked"
            safe_extract(wheel, unpacked)
            if find_pipeline_dir(unpacked) is None:
                raise EngineError(f"the wheel of {self.model} contains no spaCy pipeline")
            shutil.rmtree(target, ignore_errors=True)
            unpacked.rename(target)

    def load(self) -> None:
        spacy = _import_spacy()
        pipeline_dir = find_pipeline_dir(self._install_dir())
        if pipeline_dir is None:
            raise EngineError(
                f"spaCy pipeline {self.model!r} is not installed. "
                "Run `syntaxlab-api download-models` first."
            )
        try:
            with warnings.catch_warnings():
                # W094: the model's own spaCy pin is loose. SyntaxLab pins spaCy itself.
                warnings.filterwarnings("ignore", message=r"\[W094\]")
                nlp = spacy.load(pipeline_dir)
        except Exception as exc:  # spaCy raises many types; normalize them
            raise EngineError(f"could not load the spaCy pipeline {self.model!r}") from exc
        wanted = {*self.components, *self.shared_components}
        missing = wanted - set(nlp.pipe_names)
        if missing:
            raise EngineError(
                f"pipeline {self.model!r} has no component(s) {sorted(missing)}; "
                f"it has {nlp.pipe_names}"
            )
        nlp.select_pipes(enable=[p for p in nlp.pipe_names if p in wanted])
        if self.keep_hyphenated_words:
            keep_hyphenated_words(nlp, spacy)
        self._nlp = nlp

    def close(self) -> None:
        self._nlp = None

    # ------------------------------------------------------------------ analysis

    def analyze(self, text: str, structures: frozenset[StructureKind]) -> list[SentenceAnalysis]:
        if self._nlp is None:
            raise EngineError("engine not loaded")
        collapsed, offsets = collapse_whitespace(text)
        try:
            doc = self._nlp.make_doc(collapsed)
            if self.split_sentences:
                mark_sentence_boundaries(doc, self.abbreviations)
            doc = self._nlp(doc)  # parsing always runs: it also delimits sentences
        except Exception as exc:
            raise EngineError("spaCy failed while analyzing the text") from exc
        dependency_scheme = (
            self.scheme_for(Capability.DEPENDENCY)
            if StructureKind.DEPENDENCY in structures
            else None
        )
        return [
            normalize_span(span, text, offsets, dependency_scheme=dependency_scheme)
            for span in doc.sents
        ]


def _import_spacy() -> Any:
    try:
        import spacy
    except ImportError as exc:
        raise EngineError(
            "the 'spacy' engine needs the optional dependency: install with `uv sync --extra spacy`"
        ) from exc
    return spacy


def _required_str(options: dict[str, Any], key: str) -> str:
    value = options.pop(key, None)
    if not isinstance(value, str) or not value:
        raise EngineConfigError(f"spacy engine option {key!r} is required")
    return value


def _string_tuple(value: Any, key: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise EngineConfigError(f"spacy {key!r} must be a list of strings")
    return tuple(value)


# ---------------------------------------------------------------------- installation


def fetch(url: str, destination: Path) -> None:
    """Download ``url``, resuming after a failed or stalled attempt."""
    last_error: OSError | None = None
    for attempt in range(1, _DOWNLOAD_ATTEMPTS + 1):
        offset = destination.stat().st_size if destination.exists() else 0
        request = urllib.request.Request(url)  # noqa: S310 - the URL comes from our configuration
        if offset:
            request.add_header("Range", f"bytes={offset}-")
        try:
            with (
                urllib.request.urlopen(request, timeout=_STALL_WINDOW_S) as response,  # noqa: S310
                # 206: the server honoured the range. Otherwise it is sending the whole file.
                destination.open("ab" if response.status == 206 else "wb") as out,
            ):
                _copy_watching_for_stalls(response, out)
            return
        except urllib.error.HTTPError as exc:
            if exc.code == 416:  # nothing left to send: the file is complete
                return
            last_error = exc
        except OSError as exc:
            last_error = exc
        logger.warning("download attempt %d of %s failed: %s", attempt, url, last_error)
    raise EngineError(f"could not download {url}: {last_error}")


def _copy_watching_for_stalls(source: Any, out: Any) -> None:
    window_start = time.monotonic()
    window_bytes = 0
    while chunk := source.read(_DOWNLOAD_CHUNK):
        out.write(chunk)
        window_bytes += len(chunk)
        if time.monotonic() - window_start >= _STALL_WINDOW_S:
            if window_bytes < _STALL_MIN_BYTES:
                raise TimeoutError(f"only {window_bytes} bytes in {_STALL_WINDOW_S:.0f} s")
            window_start, window_bytes = time.monotonic(), 0


def verify_sha256(path: Path, expected: str) -> None:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_DOWNLOAD_CHUNK):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise EngineError(
            f"checksum mismatch for {path.name}: expected {expected}, got {digest.hexdigest()}"
        )


def safe_extract(wheel: Path, target: Path) -> None:
    """Unpack a wheel, refusing members that would land outside ``target``."""
    root = target.resolve()
    with zipfile.ZipFile(wheel) as archive:
        for member in archive.namelist():
            if not (root / member).resolve().is_relative_to(root):
                raise EngineError(f"unsafe path in wheel: {member!r}")
        archive.extractall(root)  # every member was checked above


def find_pipeline_dir(directory: Path) -> Path | None:
    """The directory holding the pipeline's ``config.cfg``, or None if it is not there."""
    if not directory.is_dir():
        return None
    return next((c.parent for c in sorted(directory.rglob("config.cfg"))), None)


def keep_hyphenated_words(nlp: Any, spacy: Any) -> None:
    """Remove the one tokenizer rule that splits a word at a hyphen between letters.

    spaCy's default splits *nag-aral* into ``nag - aral``, while UD Tagalog keeps such words
    whole; the parser then sees three fragments. This changes tokenization only, never an
    analysis, and its effect is measured against gold in docs/research/nlp-model-evaluation.md.
    """
    from spacy.lang.char_classes import ALPHA, HYPHENS

    rule = rf"(?<=[{ALPHA}])(?:{HYPHENS})(?=[{ALPHA}])"
    infixes = list(nlp.Defaults.infixes)
    if rule not in infixes:
        raise EngineError("spaCy's letter-hyphen-letter tokenizer rule was not found")
    nlp.tokenizer.infix_finditer = spacy.util.compile_infix_regex(
        [pattern for pattern in infixes if pattern != rule]
    ).finditer


def mark_sentence_boundaries(doc: Any, abbreviations: frozenset[str]) -> None:
    """Fix sentence boundaries at final punctuation, for the parser to respect.

    A sentence starts at the first word after ``.``, ``!`` or ``?``, and any closing punctuation
    stays with the sentence it follows. A period right after one of ``abbreviations`` ends nothing.
    Only the boundaries are set: no token, label or head within a sentence is touched.
    """
    ended = False
    for position, token in enumerate(doc):
        is_final = token.text in _SENTENCE_FINAL and not (
            token.text == "." and position > 0 and doc[position - 1].text in abbreviations
        )
        if position == 0:
            token.is_sent_start = True
        elif ended and not token.is_punct:
            token.is_sent_start = True
            ended = False
        else:
            token.is_sent_start = False
        ended = ended or is_final


# ---------------------------------------------------------------------- normalization


def collapse_whitespace(text: str) -> tuple[str, list[int]]:
    """Replace each run of whitespace with one space.

    Returns the new text and, for each of its characters, its offset in ``text``.
    """
    pieces: list[str] = []
    offsets: list[int] = []
    position = 0
    for match in _WHITESPACE.finditer(text):
        pieces.append(text[position : match.start()])
        offsets.extend(range(position, match.start()))
        pieces.append(" ")
        offsets.append(match.start())
        position = match.end()
    pieces.append(text[position:])
    offsets.extend(range(position, len(text)))
    return "".join(pieces), offsets


def normalize_span(
    span: Any, source: str, offsets: list[int], *, dependency_scheme: str | None
) -> SentenceAnalysis:
    """Convert one spaCy sentence to the SyntaxLab schema.

    ``source`` is the text as submitted and ``offsets`` maps the analyzed text back to it (see
    :func:`collapse_whitespace`). Values are copied as produced by the pipeline, with one
    convention translated: spaCy's ``ROOT`` label and self-headed root become UD's ``root`` with
    head 0.
    """
    words = list(span)
    ids = {t.i: position for position, t in enumerate(words, start=1)}
    tokens = [
        Token(
            id=ids[t.i],
            form=t.text,
            lemma=t.lemma_ or None,
            upos=t.pos_ or None,
            xpos=t.tag_ or None,
            feats=dict(t.morph.to_dict()),
            start_char=offsets[t.idx],
            end_char=offsets[t.idx + len(t.text) - 1] + 1,
        )
        for t in words
    ]

    dependency = None
    if dependency_scheme is not None:
        arcs = []
        for t in words:
            if not t.dep_:
                raise EngineError("dependency parse requested but spaCy returned no labels")
            is_root = t.dep_ == "ROOT"
            if not is_root and t.head.i not in ids:
                raise EngineError(f"word {t.text!r} depends on a word in another sentence")
            arcs.append(
                DependencyArc(
                    dependent=ids[t.i],
                    head=0 if is_root else ids[t.head.i],
                    relation="root" if is_root else t.dep_,
                )
            )
        dependency = DependencyAnalysis(scheme=dependency_scheme, arcs=arcs)

    start, end = tokens[0].start_char, tokens[-1].end_char
    return SentenceAnalysis(
        text=source[start:end],
        start_char=start,
        end_char=end,
        tokens=tokens,
        dependency=dependency,
    )
