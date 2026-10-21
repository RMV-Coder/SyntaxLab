"""Structural validation of engine output.

Every analysis passes through here before it reaches a client. A failure means the engine (or
its normalizer) is broken; the API reports ``invalid_engine_output`` instead of repairing the
structure, because a repaired tree would no longer be the parser's analysis.
"""

from __future__ import annotations

from itertools import pairwise

from syntaxlab_api.schemas.analysis import (
    ConstituencyAnalysis,
    DependencyAnalysis,
    MultiwordToken,
    SentenceAnalysis,
    Token,
)


class StructureError(ValueError):
    """Raised when an analysis violates a structural invariant."""


def validate_sentence(sentence: SentenceAnalysis) -> None:
    n = _validate_tokens(sentence.tokens)
    _validate_multiword_tokens(sentence.multiword_tokens, n)
    if sentence.dependency is not None:
        validate_dependency(sentence.dependency, n)
    if sentence.constituency is not None:
        validate_constituency(sentence.constituency, n)


def _validate_tokens(tokens: list[Token]) -> int:
    if not tokens:
        raise StructureError("sentence has no tokens")
    ids = [t.id for t in tokens]
    if ids != list(range(1, len(tokens) + 1)):
        raise StructureError(f"token ids must be 1..{len(tokens)} in order, got {ids}")
    for t in tokens:
        if not t.form:
            raise StructureError(f"token {t.id} has an empty form")
        if t.start_char is not None and t.end_char is not None and t.start_char > t.end_char:
            raise StructureError(f"token {t.id} has start_char > end_char")
    return len(tokens)


def _validate_multiword_tokens(mwts: list[MultiwordToken], n: int) -> None:
    previous_last = 0
    for m in sorted(mwts, key=lambda m: m.first):
        if not (1 <= m.first < m.last <= n):
            raise StructureError(f"multiword token {m.form!r} has invalid range {m.first}-{m.last}")
        if m.first <= previous_last:
            raise StructureError(f"multiword token {m.form!r} overlaps another")
        previous_last = m.last


def validate_dependency(dep: DependencyAnalysis, n: int, *, single_root: bool = True) -> None:
    by_dependent: dict[int, int] = {}
    for arc in dep.arcs:
        if arc.dependent in by_dependent:
            raise StructureError(f"word {arc.dependent} has more than one head")
        if not (1 <= arc.dependent <= n):
            raise StructureError(f"arc dependent {arc.dependent} out of range 1..{n}")
        if not (0 <= arc.head <= n):
            raise StructureError(f"arc head {arc.head} out of range 0..{n}")
        if arc.head == arc.dependent:
            raise StructureError(f"word {arc.dependent} is its own head")
        if not arc.relation:
            raise StructureError(f"arc to word {arc.dependent} has an empty relation")
        by_dependent[arc.dependent] = arc.head
    if len(by_dependent) != n:
        missing = sorted(set(range(1, n + 1)) - set(by_dependent))
        raise StructureError(f"words without a head: {missing}")

    roots = [d for d, h in by_dependent.items() if h == 0]
    if not roots:
        raise StructureError("dependency tree has no root")
    if single_root and len(roots) > 1:
        raise StructureError(f"dependency tree has several roots: {roots}")

    # Acyclicity: following heads from any word must reach 0 within n steps.
    for start in range(1, n + 1):
        node, steps = start, 0
        while node != 0:
            node = by_dependent[node]
            steps += 1
            if steps > n:
                raise StructureError(f"cycle in dependency tree involving word {start}")


def validate_constituency(tree: ConstituencyAnalysis, n: int) -> None:
    nodes = {}
    for node in tree.nodes:
        if node.id in nodes:
            raise StructureError(f"duplicate constituency node id {node.id!r}")
        nodes[node.id] = node
    if tree.root not in nodes:
        raise StructureError(f"root {tree.root!r} is not a node")

    parent_count: dict[str, int] = dict.fromkeys(nodes, 0)
    for node in tree.nodes:
        if not node.label:
            raise StructureError(f"node {node.id!r} has an empty label")
        if node.token_id is not None and node.children:
            raise StructureError(f"pre-terminal {node.id!r} must not have children")
        if node.token_id is None and not node.children:
            raise StructureError(f"phrase node {node.id!r} has no children")
        for child in node.children:
            if child not in nodes:
                raise StructureError(f"node {node.id!r} references unknown child {child!r}")
            parent_count[child] += 1
    if parent_count[tree.root] != 0:
        raise StructureError("root node has a parent")
    for node_id, count in parent_count.items():
        if node_id != tree.root and count != 1:
            raise StructureError(f"node {node_id!r} has {count} parents (expected 1)")

    # Depth-first walk from the root: detects cycles and unreachable nodes, collects the
    # terminal yield, and recomputes every span.
    visited: set[str] = set()
    terminal_yield: list[int] = []

    def walk(node_id: str, path: frozenset[str]) -> tuple[int, int]:
        if node_id in path:
            raise StructureError(f"cycle through node {node_id!r}")
        visited.add(node_id)
        node = nodes[node_id]
        if node.token_id is not None:
            terminal_yield.append(node.token_id)
            span = (node.token_id, node.token_id)
        else:
            child_spans = [walk(c, path | {node_id}) for c in node.children]
            for (_, prev_end), (next_start, _) in pairwise(child_spans):
                if next_start != prev_end + 1:
                    raise StructureError(f"children of {node_id!r} are not contiguous/ordered")
            span = (child_spans[0][0], child_spans[-1][1])
        if tuple(node.span) != span:
            raise StructureError(f"node {node_id!r} has span {node.span}, expected {span}")
        return span

    walk(tree.root, frozenset())
    if visited != set(nodes):
        raise StructureError(f"unreachable nodes: {sorted(set(nodes) - visited)}")
    if terminal_yield != list(range(1, n + 1)):
        raise StructureError(
            f"constituency yield {terminal_yield} does not cover words 1..{n} exactly once in order"
        )
