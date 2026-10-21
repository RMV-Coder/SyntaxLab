from __future__ import annotations

import pytest

from syntaxlab_api.analysis.validate import (
    StructureError,
    validate_constituency,
    validate_dependency,
    validate_sentence,
)
from syntaxlab_api.schemas.analysis import (
    ConstituencyAnalysis,
    ConstituencyNode,
    DependencyAnalysis,
    DependencyArc,
    MultiwordToken,
    SentenceAnalysis,
    Token,
)


def dep(*triples: tuple[int, int, str]) -> DependencyAnalysis:
    return DependencyAnalysis(
        scheme="ud-2", arcs=[DependencyArc(dependent=d, head=h, relation=r) for d, h, r in triples]
    )


def node(
    node_id: str,
    label: str,
    span: tuple[int, int],
    children: list[str] | None = None,
    token_id: int | None = None,
) -> ConstituencyNode:
    return ConstituencyNode(
        id=node_id, label=label, span=span, children=children or [], token_id=token_id
    )


# "the cat sleeps": (S (NP (DT the) (NN cat)) (VP (VBZ sleeps)))
def good_tree() -> list[ConstituencyNode]:
    return [
        node("s", "S", (1, 3), ["np", "vp"]),
        node("np", "NP", (1, 2), ["dt", "nn"]),
        node("dt", "DT", (1, 1), token_id=1),
        node("nn", "NN", (2, 2), token_id=2),
        node("vp", "VP", (3, 3), ["vbz"]),
        node("vbz", "VBZ", (3, 3), token_id=3),
    ]


def tree(nodes: list[ConstituencyNode], root: str = "s") -> ConstituencyAnalysis:
    return ConstituencyAnalysis(scheme="ptb", root=root, nodes=nodes)


class TestDependency:
    def test_valid_tree(self) -> None:
        validate_dependency(dep((1, 2, "det"), (2, 3, "nsubj"), (3, 0, "root")), 3)

    @pytest.mark.parametrize(
        ("arcs", "message"),
        [
            ([(1, 2, "det"), (1, 3, "x"), (2, 3, "nsubj"), (3, 0, "root")], "more than one head"),
            ([(1, 2, "det"), (3, 0, "root")], "without a head"),
            ([(1, 4, "det"), (2, 3, "nsubj"), (3, 0, "root")], "out of range"),
            ([(1, 1, "det"), (2, 3, "nsubj"), (3, 0, "root")], "own head"),
            ([(1, 2, "det"), (2, 1, "nsubj"), (3, 0, "root")], "cycle"),
            ([(1, 0, "root"), (2, 3, "nsubj"), (3, 0, "root")], "several roots"),
            ([(1, 2, "det"), (2, 3, "nsubj"), (3, 1, "x")], "no root"),
            ([(1, 2, ""), (2, 3, "nsubj"), (3, 0, "root")], "empty relation"),
        ],
    )
    def test_invalid_trees(self, arcs: list[tuple[int, int, str]], message: str) -> None:
        with pytest.raises(StructureError, match=message):
            validate_dependency(dep(*arcs), 3)

    def test_multiple_roots_allowed_when_requested(self) -> None:
        validate_dependency(dep((1, 0, "root"), (2, 0, "root")), 2, single_root=False)


class TestConstituency:
    def test_valid_tree(self) -> None:
        validate_constituency(tree(good_tree()), 3)

    def test_duplicate_ids(self) -> None:
        nodes = [*good_tree(), node("dt", "DT", (1, 1), token_id=1)]
        with pytest.raises(StructureError, match="duplicate"):
            validate_constituency(tree(nodes), 3)

    def test_unknown_child(self) -> None:
        nodes = good_tree()
        nodes[0] = node("s", "S", (1, 3), ["np", "missing"])
        with pytest.raises(StructureError, match="unknown child"):
            validate_constituency(tree(nodes), 3)

    def test_node_with_two_parents(self) -> None:
        nodes = good_tree()
        nodes[4] = node("vp", "VP", (3, 3), ["vbz", "nn"])
        with pytest.raises(StructureError, match="2 parents"):
            validate_constituency(tree(nodes), 3)

    def test_unreachable_node(self) -> None:
        nodes = [*good_tree(), node("orphan", "X", (1, 1), token_id=1)]
        with pytest.raises(StructureError, match="0 parents"):
            validate_constituency(tree(nodes), 3)

    def test_cycle(self) -> None:
        nodes = good_tree()
        nodes[4] = node("vp", "VP", (3, 3), ["vbz", "s2"])
        nodes.append(node("s2", "X", (3, 3), ["vp"]))
        with pytest.raises(StructureError):
            validate_constituency(tree(nodes), 3)

    def test_wrong_span(self) -> None:
        nodes = good_tree()
        nodes[1] = node("np", "NP", (1, 3), ["dt", "nn"])
        with pytest.raises(StructureError, match="span"):
            validate_constituency(tree(nodes), 3)

    def test_yield_must_cover_all_words(self) -> None:
        with pytest.raises(StructureError, match="yield"):
            validate_constituency(tree(good_tree()), 4)

    def test_children_out_of_order(self) -> None:
        nodes = good_tree()
        nodes[0] = node("s", "S", (1, 3), ["vp", "np"])
        with pytest.raises(StructureError, match="contiguous"):
            validate_constituency(tree(nodes), 3)

    def test_preterminal_with_children(self) -> None:
        nodes = good_tree()
        nodes[2] = ConstituencyNode(id="dt", label="DT", span=(1, 1), token_id=1, children=["nn"])
        with pytest.raises(StructureError, match="must not have children"):
            validate_constituency(tree(nodes), 3)

    def test_phrase_without_children(self) -> None:
        nodes = good_tree()
        nodes[4] = node("vp", "VP", (3, 3))
        with pytest.raises(StructureError, match="no children"):
            validate_constituency(tree(nodes), 3)


class TestSentence:
    def tokens(self, n: int) -> list[Token]:
        return [Token(id=i, form=f"w{i}") for i in range(1, n + 1)]

    def test_token_ids_must_be_sequential(self) -> None:
        tokens = [Token(id=1, form="a"), Token(id=3, form="b")]
        with pytest.raises(StructureError, match="token ids"):
            validate_sentence(SentenceAnalysis(text="a b", tokens=tokens))

    def test_empty_sentence(self) -> None:
        with pytest.raises(StructureError, match="no tokens"):
            validate_sentence(SentenceAnalysis(text="", tokens=[]))

    @pytest.mark.parametrize(("first", "last"), [(2, 2), (0, 1), (2, 4)])
    def test_bad_multiword_range(self, first: int, last: int) -> None:
        mwt = MultiwordToken(first=max(first, 1), last=last, form="x")
        sentence = SentenceAnalysis(text="x", tokens=self.tokens(3), multiword_tokens=[mwt])
        with pytest.raises(StructureError, match="invalid range"):
            validate_sentence(sentence)

    def test_overlapping_multiword_tokens(self) -> None:
        mwts = [
            MultiwordToken(first=1, last=2, form="ab"),
            MultiwordToken(first=2, last=3, form="bc"),
        ]
        sentence = SentenceAnalysis(text="x", tokens=self.tokens(3), multiword_tokens=mwts)
        with pytest.raises(StructureError, match="overlaps"):
            validate_sentence(sentence)
