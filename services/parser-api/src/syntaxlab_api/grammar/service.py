"""Glue between the Earley implementation and the API schemas."""

from __future__ import annotations

from syntaxlab_api import errors
from syntaxlab_api.grammar.earley import Earley, Event, Forest, ItemRef, Tree
from syntaxlab_api.grammar.grammar import (
    Diagnostic,
    Grammar,
    compile_grammar,
    matches,
    parse_grammar,
    tokenize,
)
from syntaxlab_api.schemas.grammar import (
    ChartItemOut,
    DerivationTree,
    GrammarDiagnostic,
    GrammarRule,
    GrammarSummary,
    GrammarSymbol,
    ItemRefOut,
    ParseGrammarResponse,
    TraceEventOut,
    ValidateGrammarResponse,
)

MAX_TOKENS = 20
TREE_COUNT_CAP = 10**12


def _diagnostics(problems: list[Diagnostic]) -> list[GrammarDiagnostic]:
    return [
        GrammarDiagnostic(severity=p.severity, code=p.code, message=p.message, line=p.line)
        for p in problems
    ]


def summarize(grammar: Grammar) -> GrammarSummary:
    return GrammarSummary(
        start=grammar.start,
        rules=[
            GrammarRule(
                index=r.index,
                lhs=r.lhs,
                rhs=[GrammarSymbol(kind=s.kind, value=s.value) for s in r.rhs],
                text=r.text(),
                line=r.line,
            )
            for r in grammar.rules
        ],
        nonterminals=grammar.nonterminals,
        terminals=grammar.terminals,
        nullable=sorted(grammar.nullable),
    )


def validate(text: str) -> ValidateGrammarResponse:
    grammar, problems = compile_grammar(text)
    if grammar is None:
        # Still describe what parsed, if the text was syntactically valid.
        parsed, _ = parse_grammar(text)
        return ValidateGrammarResponse(
            valid=False,
            diagnostics=_diagnostics(problems),
            grammar=summarize(parsed) if parsed else None,
        )
    return ValidateGrammarResponse(
        valid=True, diagnostics=_diagnostics(problems), grammar=summarize(grammar)
    )


def _ref(ref: ItemRef | None) -> ItemRefOut | None:
    return ItemRefOut(set=ref.set, index=ref.index) if ref else None


def _event(event: Event) -> TraceEventOut:
    return TraceEventOut(
        step=event.step,
        kind=event.kind,
        set=event.set,
        item=_ref(event.item),
        added=event.added,
        cause=_ref(event.cause),
        completed=_ref(event.completed),
        symbol=event.symbol,
        token=event.token,
        rule=event.rule,
    )


def _tree(tree: Tree) -> DerivationTree:
    return DerivationTree(
        symbol=tree.symbol,
        kind="terminal" if tree.token is not None else "nonterminal",
        start=tree.start,
        end=tree.end,
        rule=tree.rule,
        token=tree.token,
        children=[_tree(c) for c in tree.children],
    )


def parse(grammar_text: str, sentence: str, max_trees: int) -> ParseGrammarResponse:
    grammar, problems = compile_grammar(grammar_text)
    if grammar is None:
        raise errors.InvalidGrammar(
            "The grammar has errors. Fix them before parsing.",
            details={"diagnostics": [d.model_dump() for d in _diagnostics(problems)]},
        )
    tokens = tokenize(sentence)
    if not tokens:
        raise errors.EmptyText("Enter a sentence to parse.")
    if len(tokens) > MAX_TOKENS:
        raise errors.TooManyWords(
            f"The Algorithm Lab parses up to {MAX_TOKENS} words ({len(tokens)} given).",
            details={"words": len(tokens), "max_words": MAX_TOKENS},
        )

    result = Earley(grammar).parse(tokens)
    forest = Forest(grammar, result)
    count = forest.tree_count()
    return ParseGrammarResponse(
        grammar=summarize(grammar),
        diagnostics=_diagnostics(problems),
        tokens=tokens,
        unknown_tokens=[
            i for i, t in enumerate(tokens) if not any(matches(w, t) for w in grammar.terminals)
        ],
        accepted=result.accepted,
        tree_count=min(count, TREE_COUNT_CAP),
        tree_count_capped=count > TREE_COUNT_CAP,
        trees=[_tree(t) for t in forest.trees(max_trees)],
        chart=[
            [
                ChartItemOut(rule=i.rule, dot=i.dot, origin=i.origin, end=i.end, step=i.step)
                for i in column
            ]
            for column in result.chart
        ],
        trace=[_event(e) for e in result.events],
        trace_truncated=result.events_truncated,
    )
