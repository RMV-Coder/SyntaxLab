"""Stanza -> SyntaxLab normalization, using hand-built Stanza documents (no models needed)."""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("stanza")

from stanza.models.common.doc import Document
from stanza.models.constituency import tree_reader

from syntaxlab_api.analysis.validate import validate_sentence
from syntaxlab_api.engines.base import EngineConfigError, EngineContext, EngineError
from syntaxlab_api.engines.stanza_engine import (
    StanzaEngine,
    convert_tree,
    normalize_sentence,
    parse_feats,
)
from syntaxlab_api.schemas.analysis import Capability

# "I don't run." with the multiword token "don't" -> do + n't, as Stanza's English MWT expands it.
WORDS: list[dict[str, Any]] = [
    {
        "id": 1,
        "text": "I",
        "lemma": "I",
        "upos": "PRON",
        "xpos": "PRP",
        "feats": "Case=Nom|Number=Sing|Person=1|PronType=Prs",
        "head": 4,
        "deprel": "nsubj",
        "start_char": 0,
        "end_char": 1,
    },
    {"id": (2, 3), "text": "don't", "start_char": 2, "end_char": 7},
    {
        "id": 2,
        "text": "do",
        "lemma": "do",
        "upos": "AUX",
        "xpos": "VBP",
        "feats": "Mood=Ind",
        "head": 4,
        "deprel": "aux",
    },
    {
        "id": 3,
        "text": "n't",
        "lemma": "not",
        "upos": "PART",
        "xpos": "RB",
        "feats": "Polarity=Neg",
        "head": 4,
        "deprel": "advmod",
    },
    {
        "id": 4,
        "text": "run",
        "lemma": "run",
        "upos": "VERB",
        "xpos": "VB",
        "feats": "VerbForm=Inf",
        "head": 0,
        "deprel": "root",
        "start_char": 8,
        "end_char": 11,
    },
    {
        "id": 5,
        "text": ".",
        "lemma": ".",
        "upos": "PUNCT",
        "xpos": ".",
        "head": 4,
        "deprel": "punct",
        "start_char": 11,
        "end_char": 12,
    },
]
TREE = "(ROOT (S (NP (PRP I)) (VP (VBP do) (RB n't) (VP (VB run))) (. .)))"


def make_sentence(tree: str | None = TREE) -> Any:
    doc = Document([WORDS], text="I don't run.")
    sentence = doc.sentences[0]
    if tree is not None:
        sentence.constituency = tree_reader.read_trees(tree)[0]
    return sentence


class TestNormalizeSentence:
    def test_tokens_preserve_stanza_values(self) -> None:
        result = normalize_sentence(
            make_sentence(), dependency_scheme="ud-2", constituency_scheme="ptb-revised"
        )
        assert [t.form for t in result.tokens] == ["I", "do", "n't", "run", "."]
        first = result.tokens[0]
        assert (first.lemma, first.upos, first.xpos) == ("I", "PRON", "PRP")
        assert first.feats == {"Case": "Nom", "Number": "Sing", "Person": "1", "PronType": "Prs"}
        assert result.tokens[4].feats == {}

    def test_multiword_token_kept(self) -> None:
        result = normalize_sentence(
            make_sentence(), dependency_scheme=None, constituency_scheme=None
        )
        assert len(result.multiword_tokens) == 1
        mwt = result.multiword_tokens[0]
        assert (mwt.first, mwt.last, mwt.form, mwt.start_char, mwt.end_char) == (
            2,
            3,
            "don't",
            2,
            7,
        )

    def test_dependency_arcs_copied_verbatim(self) -> None:
        result = normalize_sentence(
            make_sentence(), dependency_scheme="ud-2", constituency_scheme=None
        )
        assert result.dependency is not None
        assert result.dependency.scheme == "ud-2"
        assert [(a.dependent, a.head, a.relation) for a in result.dependency.arcs] == [
            (1, 4, "nsubj"),
            (2, 4, "aux"),
            (3, 4, "advmod"),
            (4, 0, "root"),
            (5, 4, "punct"),
        ]
        assert result.constituency is None

    def test_constituency_tree_converted_with_spans(self) -> None:
        result = normalize_sentence(
            make_sentence(), dependency_scheme=None, constituency_scheme="ptb-revised"
        )
        tree = result.constituency
        assert tree is not None
        nodes = {n.id: n for n in tree.nodes}
        root = nodes[tree.root]
        assert (root.label, root.span) == ("ROOT", (1, 5))
        preterminals = [(n.label, n.token_id) for n in tree.nodes if n.token_id is not None]
        assert preterminals == [("PRP", 1), ("VBP", 2), ("RB", 3), ("VB", 4), (".", 5)]
        vp = next(n for n in tree.nodes if n.label == "VP" and n.span == (2, 4))
        assert [nodes[c].label for c in vp.children] == ["VBP", "RB", "VP"]

    def test_output_passes_structural_validation(self) -> None:
        validate_sentence(
            normalize_sentence(
                make_sentence(), dependency_scheme="ud-2", constituency_scheme="ptb-revised"
            )
        )

    def test_missing_tree_is_an_error_not_a_fallback(self) -> None:
        with pytest.raises(EngineError, match="no tree"):
            normalize_sentence(
                make_sentence(tree=None), dependency_scheme=None, constituency_scheme="ptb-revised"
            )


class TestConvertTree:
    def read(self, text: str) -> Any:
        return tree_reader.read_trees(text)[0]

    def test_leaf_must_match_word(self) -> None:
        with pytest.raises(EngineError, match="does not match"):
            convert_tree(self.read("(ROOT (NP (NN cat)))"), ["dog"], scheme="ptb")

    def test_tree_with_too_few_leaves(self) -> None:
        with pytest.raises(EngineError, match="covers 1 words"):
            convert_tree(self.read("(ROOT (NP (NN cat)))"), ["cat", "."], scheme="ptb")

    def test_tree_with_too_many_leaves(self) -> None:
        with pytest.raises(EngineError, match="more leaves"):
            convert_tree(self.read("(ROOT (NP (DT the) (NN cat)))"), ["the"], scheme="ptb")

    def test_leaf_outside_preterminal_rejected(self) -> None:
        # Stanza's reader refuses such trees, so build one directly: (ROOT (NP the (NN cat)))
        from stanza.models.constituency.parse_tree import Tree

        mixed = Tree("ROOT", [Tree("NP", [Tree("the"), Tree("NN", [Tree("cat")])])])
        with pytest.raises(EngineError, match="not under a pre-terminal"):
            convert_tree(mixed, ["the", "cat"], scheme="ptb")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, {}), ("_", {}), ("", {}), ("A=B", {"A": "B"}), ("A=B|C=D,E", {"A": "B", "C": "D,E"})],
)
def test_parse_feats(raw: str | None, expected: dict[str, str]) -> None:
    assert parse_feats(raw) == expected


def test_parse_feats_rejects_malformed() -> None:
    with pytest.raises(EngineError):
        parse_feats("A")


class TestEngineOptions:
    def engine(self, **options: Any) -> StanzaEngine:
        return StanzaEngine(EngineContext(language="en", options=options))

    def test_capabilities_follow_processors(self) -> None:
        caps = self.engine().capabilities()
        assert set(caps) == set(Capability)
        limited = self.engine(processors=["tokenize", "pos", "lemma", "depparse"]).capabilities()
        assert Capability.CONSTITUENCY not in limited
        assert Capability.DEPENDENCY in limited

    def test_unknown_option_rejected(self) -> None:
        with pytest.raises(EngineConfigError, match="unknown stanza engine options"):
            self.engine(pacakge="default")

    def test_unknown_processor_rejected(self) -> None:
        with pytest.raises(EngineConfigError, match="unsupported"):
            self.engine(processors=["tokenize", "sentiment"])

    def test_tokenize_required(self) -> None:
        with pytest.raises(EngineConfigError, match="tokenize"):
            self.engine(processors=["pos"])

    def test_analyze_before_load_fails(self) -> None:
        with pytest.raises(EngineError, match="not loaded"):
            self.engine().analyze("Hi.", frozenset())
