"""Checking answers against answer keys, with feedback that does not overclaim.

* POS / dependency: compared with one expert annotation. Feedback reports agreement with that
  annotation; it cannot know whether a different analysis would also be defensible, and the UI
  says so.
* Constituency: compared with **all** parses the grammar allows (ε-constituents removed, since
  students do not draw empty nodes). A tree matching any of them is correct. Otherwise feedback
  is relative to the closest parse, and every extra constituent is classified as "valid in
  another reading" or "licensed by no parse of this sentence".
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from syntaxlab_api import errors
from syntaxlab_api.grammar.earley import Earley, Forest, Tree
from syntaxlab_api.grammar.grammar import Grammar, Symbol, compile_grammar, matches, tokenize
from syntaxlab_api.learning.exercises import ConstituencyExercise, DependencyExercise, PosExercise
from syntaxlab_api.schemas.grammar import DerivationTree
from syntaxlab_api.schemas.learning import (
    ConstituencyAnswer,
    ConstituencyFeedback,
    ConstituentFeedback,
    ConstituentStatus,
    DependencyAnswer,
    DependencyFeedback,
    DependencyItem,
    PosAnswer,
    PosFeedback,
    PosItem,
    StructureProblem,
    TokenStatus,
)

MAX_PARSES_COMPARED = 200


# ---------------------------------------------------------------------- POS and dependency


def check_pos(exercise: PosExercise, answer: PosAnswer) -> PosFeedback:
    if len(answer.tags) != len(exercise.tokens):
        raise errors.InvalidInput(
            f"Expected {len(exercise.tokens)} tags, got {len(answer.tags)}.",
        )
    items = []
    for token, given in zip(exercise.tokens, answer.tags, strict=True):
        status: TokenStatus = (
            "unanswered" if not given else "correct" if given == token.upos else "incorrect"
        )
        items.append(
            PosItem(token=token.id, given=given or None, expected=token.upos, status=status)
        )
    return PosFeedback(
        kind="pos",
        correct=sum(i.status == "correct" for i in items),
        total=len(items),
        items=items,
    )


def _base(relation: str) -> str:
    return relation.split(":", 1)[0]


def check_dependency(exercise: DependencyExercise, answer: DependencyAnswer) -> DependencyFeedback:
    given = {arc.dependent: arc for arc in answer.arcs}
    if set(given) != {t.id for t in exercise.tokens}:
        raise errors.InvalidInput("Give exactly one entry per word.")
    items = []
    for token in exercise.tokens:
        arc = given[token.id]
        relation = "root" if arc.head == 0 else arc.relation
        status: TokenStatus
        if not relation:
            status = "unanswered"
        elif relation == token.deprel:
            status = "correct"
        elif _base(relation) == _base(token.deprel):
            status = "partial"
        else:
            status = "incorrect"
        items.append(
            DependencyItem(
                token=token.id,
                given_head=arc.head,
                given_relation=relation,
                expected_head=token.head,
                expected_relation=token.deprel,
                head_correct=arc.head == token.head,
                relation_status=status,
            )
        )
    return DependencyFeedback(
        kind="dependency",
        heads_correct=sum(i.head_correct for i in items),
        relations_correct=sum(i.relation_status == "correct" for i in items),
        total=len(items),
        items=items,
    )


# ---------------------------------------------------------------------- constituency

Canon = tuple[object, ...]
Span = tuple[str, int, int]


@dataclass
class _Node:
    label: str
    start: int
    end: int
    index: int
    children: list[_Node] = field(default_factory=list)


def _prune_empty(tree: Tree) -> Tree | None:
    """Remove ε-constituents (nonterminals covering no words)."""
    if tree.token is None and tree.start == tree.end:
        return None
    kept = [c for c in (_prune_empty(c) for c in tree.children) if c is not None]
    return Tree(tree.symbol, tree.start, tree.end, tree.rule, tree.token, kept)


def _canon_parse(tree: Tree) -> Canon:
    if tree.token is not None:
        return ("w", tree.token)
    return (tree.symbol, tree.start, tree.end, tuple(_canon_parse(c) for c in tree.children))


def _spans_parse(tree: Tree) -> Counter[Span]:
    spans: Counter[Span] = Counter()
    if tree.token is None:
        spans[(tree.symbol, tree.start, tree.end)] += 1
        for c in tree.children:
            spans += _spans_parse(c)
    return spans


def _canon_student(node: _Node) -> Canon:
    covered = {i for c in node.children for i in range(c.start, c.end)}
    items: list[tuple[int, Canon]] = [(c.start, _canon_student(c)) for c in node.children]
    items += [(i, ("w", i)) for i in range(node.start, node.end) if i not in covered]
    return (
        node.label,
        node.start,
        node.end,
        tuple(c for _, c in sorted(items, key=lambda x: x[0])),
    )


def _to_schema(tree: Tree) -> DerivationTree:
    return DerivationTree(
        symbol=tree.symbol,
        kind="terminal" if tree.token is not None else "nonterminal",
        start=tree.start,
        end=tree.end,
        rule=tree.rule,
        token=tree.token,
        children=[_to_schema(c) for c in tree.children],
    )


def _rule_allows(grammar: Grammar, lhs: str, rhs: list[tuple[str, str]]) -> bool:
    """Does some rule lhs → … produce rhs, allowing nullable categories to be left out?"""

    def fits(rule_rhs: tuple[Symbol, ...]) -> bool:
        # Align rule symbols with the student's sequence; nullable nonterminals may be skipped.
        reachable = {0}
        for sym in rule_rhs:
            nxt: set[int] = set()
            for j in reachable:
                if sym.kind == "nonterminal" and sym.value in grammar.nullable:
                    nxt.add(j)
                if j < len(rhs):
                    kind, value = rhs[j]
                    if sym.kind == "nonterminal" and kind == "n" and value == sym.value:
                        nxt.add(j + 1)
                    if sym.kind == "terminal" and kind == "t" and matches(sym.value, value):
                        nxt.add(j + 1)
            reachable = nxt
        return len(rhs) in reachable

    return any(fits(rule.rhs) for rule in grammar.by_lhs.get(lhs, []))


def _rule_text(lhs: str, rhs: list[tuple[str, str]]) -> str:
    parts = [value if kind == "n" else f'"{value}"' for kind, value in rhs]
    return f"{lhs} → {' '.join(parts)}"


def check_constituency(
    exercise: ConstituencyExercise, grammar_text: str, answer: ConstituencyAnswer
) -> ConstituencyFeedback:
    grammar, _ = compile_grammar(grammar_text)
    assert grammar is not None  # preset grammars are validated at startup
    tokens = tokenize(exercise.sentence)
    n = len(tokens)
    problems: list[StructureProblem] = []

    def problem(code: str, **kw: object) -> None:
        problems.append(
            StructureProblem.model_validate(
                {
                    "code": code,
                    "constituent": None,
                    "label": None,
                    "rule": None,
                    "words": None,
                    **kw,
                }
            )
        )

    def words(start: int, end: int) -> str:
        return " ".join(tokens[start:end])

    # 1. Student nodes, in canonical nesting order.
    nodes: list[_Node] = []
    for i, c in enumerate(answer.constituents):
        if not (0 <= c.start < c.end <= n):
            problem("out_of_range", constituent=i, label=c.label)
            continue
        nodes.append(_Node(c.label, c.start, c.end, i))
    for a in nodes:
        for b in nodes:
            if a.start < b.start < a.end < b.end:
                problem("crossing", constituent=b.index, label=b.label, words=words(b.start, b.end))

    # 2. Build the tree by containment (identical spans: earlier entries dominate later ones).
    roots: list[_Node] = []
    stack: list[_Node] = []
    for node in sorted(nodes, key=lambda x: (x.start, -x.end, x.index)):
        while stack and not (stack[-1].start <= node.start and node.end <= stack[-1].end):
            stack.pop()
        (stack[-1].children if stack else roots).append(node)
        stack.append(node)
    # Out-of-range entries are set aside (and reported); crossing brackets make a tree impossible.
    structural_ok = not any(p.code == "crossing" for p in problems)
    if not any(r.start == 0 and r.end == n for r in roots):
        problem("no_root", words=words(0, n))
        structural_ok = False
    elif len(roots) > 1:
        problem("several_roots")
        structural_ok = False
    covered = {i for node in nodes for i in range(node.start, node.end)}
    for i in range(n):
        if i not in covered:
            problem("uncovered_word", words=tokens[i])

    # 3. Rule-by-rule check of the student's tree against the grammar.
    if structural_ok:

        def visit(node: _Node) -> None:
            child_cover = {i for c in node.children for i in range(c.start, c.end)}
            items: list[tuple[int, tuple[str, str]]] = [
                (c.start, ("n", c.label)) for c in node.children
            ]
            items += [
                (i, ("t", tokens[i])) for i in range(node.start, node.end) if i not in child_cover
            ]
            rhs = [sym for _, sym in sorted(items, key=lambda x: x[0])]
            if node.label not in grammar.by_lhs:
                problem("unknown_category", constituent=node.index, label=node.label)
            elif not _rule_allows(grammar, node.label, rhs):
                problem(
                    "no_rule",
                    constituent=node.index,
                    label=node.label,
                    rule=_rule_text(node.label, rhs),
                    words=words(node.start, node.end),
                )
            for c in node.children:
                visit(c)

        visit(roots[0])

    # 4. All parses of the sentence (ε removed, duplicates merged), and comparison.
    forest = Forest(grammar, Earley(grammar).parse(tokens))
    parse_count = forest.tree_count()
    parses: list[Tree] = []
    seen: set[Canon] = set()
    for tree in forest.trees(limit=MAX_PARSES_COMPARED):
        pruned = _prune_empty(tree)
        if pruned is None:
            continue
        canon = _canon_parse(pruned)
        if canon not in seen:
            seen.add(canon)
            parses.append(pruned)

    student_spans: Counter[Span] = Counter((x.label, x.start, x.end) for x in nodes)
    parse_spans = [_spans_parse(p) for p in parses]
    any_parse: set[Span] = set().union(*parse_spans) if parse_spans else set()

    matched = None
    if structural_ok and len(roots) == 1:
        student_canon = _canon_student(roots[0])
        matched = next((i for i, p in enumerate(parses) if _canon_parse(p) == student_canon), None)

    def f1(spans: Counter[Span]) -> float:
        overlap = sum((spans & student_spans).values())
        total = sum(spans.values()) + sum(student_spans.values())
        return 2 * overlap / total if total else 0.0

    closest = (
        matched
        if matched is not None
        else (max(range(len(parses)), key=lambda i: (f1(parse_spans[i]), -i)) if parses else None)
    )
    reference_spans = parse_spans[closest] if closest is not None else Counter()
    correct = student_spans & reference_spans

    feedback: list[ConstituentFeedback] = []
    remaining = Counter(correct)
    for node in sorted(nodes, key=lambda x: (x.start, -x.end, x.index)):
        span = (node.label, node.start, node.end)
        status: ConstituentStatus
        if remaining[span] > 0:
            remaining[span] -= 1
            status = "correct"
        elif span in any_parse:
            status = "other_reading"
        else:
            status = "unlicensed"
        feedback.append(
            ConstituentFeedback(label=node.label, start=node.start, end=node.end, status=status)
        )
    for (label, start, end), count in sorted(
        (reference_spans - student_spans).items(), key=lambda kv: (kv[0][1], -kv[0][2])
    ):
        feedback.extend(
            ConstituentFeedback(label=label, start=start, end=end, status="missing")
            for _ in range(count)
        )

    student_total = sum(student_spans.values())
    reference_total = sum(reference_spans.values())
    overlap = sum(correct.values())
    has_errors = any(p.code != "no_rule" and p.code != "unknown_category" for p in problems)
    return ConstituencyFeedback(
        kind="constituency",
        status="matches" if matched is not None else "invalid" if has_errors else "partial",
        parse_count=parse_count,
        parses_compared=len(parses),
        matched_parse=matched + 1 if matched is not None else None,
        closest_parse=closest + 1 if closest is not None else None,
        precision=round(overlap / student_total, 4) if student_total else 0.0,
        recall=round(overlap / reference_total, 4) if reference_total else 0.0,
        constituents=feedback,
        problems=problems,
        reference=_to_schema(parses[closest]) if closest is not None else None,
    )


def spans_of(tree: Tree) -> list[Span]:
    """Labelled spans of a parse (pre-order), e.g. to build a correct answer in tests."""
    out: list[Span] = []

    def visit(t: Tree) -> None:
        if t.token is None:
            out.append((t.symbol, t.start, t.end))
            for c in t.children:
                visit(c)

    visit(tree)
    return out
