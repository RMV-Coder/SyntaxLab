"""Context-free grammars for the Algorithm Lab: notation, parsing and validation.

Notation (one rule per line; ``#`` starts a comment)::

    S   -> NP VP
    NP  -> Det N | NP PP | "I"
    N'  -> Adj N'            # primes are allowed in nonterminal names (X-bar style)
    Det -> "the" | 'a'
    Opt -> ε                 # empty right-hand side (also: "" or '')
        | "maybe"            # a line starting with | continues the previous rule

- Nonterminals are bare identifiers; terminals are quoted words (no spaces inside).
- The left-hand side of the first rule is the start symbol.
- ``->`` and ``→`` are both accepted.

Validation reports problems with line numbers. *Errors* make a grammar unusable (undefined
symbols, cycles that would give infinitely many parses, size limits); *warnings* point out
rules that can never take part in a parse.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal

MAX_RULES = 200
MAX_RHS = 12
MAX_SYMBOL_LENGTH = 32

AUGMENTED_START = "γ"

_NONTERMINAL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*'*$")
_TERMINAL = re.compile(r"""^(?:"([^"\s]*)"|'([^'\s]*)')$""")
_ARROW = re.compile(r"\s*(?:->|→)\s*")
_EPSILON = {"ε", "ϵ"}

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Symbol:
    kind: Literal["nonterminal", "terminal"]
    value: str

    def __str__(self) -> str:
        return self.value if self.kind == "nonterminal" else f'"{self.value}"'


@dataclass(frozen=True)
class Rule:
    index: int
    lhs: str
    rhs: tuple[Symbol, ...]
    line: int | None = None

    def text(self, dot: int | None = None) -> str:
        parts = [str(s) for s in self.rhs]
        if dot is not None:
            parts.insert(dot, "•")
        return f"{self.lhs} → {' '.join(parts) if parts else 'ε'}"


@dataclass(frozen=True)
class Diagnostic:
    severity: Severity
    code: str
    message: str
    line: int | None = None


@dataclass
class Grammar:
    """A parsed grammar. ``rules[0]`` is the augmented rule ``γ → start``."""

    rules: list[Rule]
    start: str
    nonterminals: list[str] = field(default_factory=list)
    terminals: list[str] = field(default_factory=list)
    by_lhs: dict[str, list[Rule]] = field(default_factory=dict)
    nullable: frozenset[str] = frozenset()

    @property
    def user_rules(self) -> list[Rule]:
        return self.rules[1:]


class GrammarSyntaxError(ValueError):
    def __init__(self, diagnostics: list[Diagnostic]) -> None:
        super().__init__("; ".join(d.message for d in diagnostics))
        self.diagnostics = diagnostics


# ---------------------------------------------------------------------- parsing


def _parse_rhs(text: str, line: int) -> tuple[tuple[Symbol, ...], list[Diagnostic]]:
    problems: list[Diagnostic] = []
    symbols: list[Symbol] = []
    pieces = text.split()
    if len(pieces) == 1 and (pieces[0] in _EPSILON or pieces[0] in ('""', "''")):
        return (), problems
    for piece in pieces:
        if piece in _EPSILON:
            problems.append(
                Diagnostic(
                    "error",
                    "epsilon_not_alone",
                    "ε must be the only symbol of an alternative.",
                    line,
                )
            )
            continue
        if terminal := _TERMINAL.match(piece):
            word = terminal.group(1) if terminal.group(1) is not None else terminal.group(2)
            if not word:
                problems.append(
                    Diagnostic(
                        "error",
                        "empty_terminal",
                        'Use ε (not "") inside a longer alternative.',
                        line,
                    )
                )
                continue
            symbols.append(Symbol("terminal", word))
        elif _NONTERMINAL.match(piece):
            symbols.append(Symbol("nonterminal", piece))
        else:
            problems.append(
                Diagnostic(
                    "error",
                    "bad_symbol",
                    f"“{piece}” is neither a nonterminal name nor a quoted word.",
                    line,
                )
            )
    if not pieces:
        problems.append(
            Diagnostic(
                "error", "empty_alternative", "Empty alternative: write ε for an empty rule.", line
            )
        )
    return tuple(symbols), problems


def _strip_comment(line: str) -> str:
    """Remove a ``#`` comment, ignoring ``#`` inside quoted words."""
    quote: str | None = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'" and (i == 0 or line[i - 1].isspace() or line[i - 1] == "|"):
            quote = ch  # a quote opens a word only at the start of a token (not in N')
        elif ch == "#":
            return line[:i]
    return line


def parse_grammar(text: str) -> tuple[Grammar | None, list[Diagnostic]]:
    """Parse grammar notation. Returns ``(None, errors)`` on syntax errors."""
    problems: list[Diagnostic] = []
    raw_rules: list[tuple[str, tuple[Symbol, ...], int]] = []
    current_lhs: str | None = None

    for number, raw in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw).strip()
        if not line:
            continue
        if line.startswith("|"):
            if current_lhs is None:
                problems.append(
                    Diagnostic(
                        "error",
                        "dangling_alternative",
                        "“|” continues a rule, but no rule precedes it.",
                        number,
                    )
                )
                continue
            lhs, rhs_text = current_lhs, line[1:]
        else:
            parts = _ARROW.split(line, maxsplit=1)
            if len(parts) != 2:
                problems.append(
                    Diagnostic(
                        "error", "missing_arrow", "Expected a rule like “NP -> Det N”.", number
                    )
                )
                continue
            lhs, rhs_text = parts[0].strip(), parts[1]
            if not _NONTERMINAL.match(lhs):
                problems.append(
                    Diagnostic(
                        "error",
                        "bad_lhs",
                        f"“{lhs}” cannot be a left-hand side: use a nonterminal name.",
                        number,
                    )
                )
                continue
            current_lhs = lhs
        for alternative in rhs_text.split("|"):
            rhs, alt_problems = _parse_rhs(alternative, number)
            problems.extend(alt_problems)
            if not alt_problems:
                raw_rules.append((lhs, rhs, number))

    if problems:
        return None, problems
    if not raw_rules:
        return None, [Diagnostic("error", "no_rules", "The grammar has no rules.")]

    start = raw_rules[0][0]
    rules = [Rule(0, AUGMENTED_START, (Symbol("nonterminal", start),))]
    seen: set[tuple[str, tuple[Symbol, ...]]] = set()
    duplicates: list[Diagnostic] = []
    for lhs, rhs, number in raw_rules:
        if (lhs, rhs) in seen:
            duplicates.append(
                Diagnostic(
                    "warning",
                    "duplicate_rule",
                    f"Duplicate rule {Rule(0, lhs, rhs).text()} ignored.",
                    number,
                )
            )
            continue
        seen.add((lhs, rhs))
        rules.append(Rule(len(rules), lhs, rhs, number))

    by_lhs: dict[str, list[Rule]] = defaultdict(list)
    for rule in rules[1:]:
        by_lhs[rule.lhs].append(rule)
    nonterminals = list(dict.fromkeys(r.lhs for r in rules[1:]))
    terminals = list(
        dict.fromkeys(s.value for r in rules[1:] for s in r.rhs if s.kind == "terminal")
    )
    grammar = Grammar(
        rules=rules,
        start=start,
        nonterminals=nonterminals,
        terminals=terminals,
        by_lhs=dict(by_lhs),
        nullable=_nullable(rules[1:]),
    )
    return grammar, duplicates


# ---------------------------------------------------------------------- analysis


def _nullable(rules: list[Rule]) -> frozenset[str]:
    nullable: set[str] = set()
    changed = True
    while changed:
        changed = False
        for rule in rules:
            if rule.lhs in nullable:
                continue
            if all(s.kind == "nonterminal" and s.value in nullable for s in rule.rhs):
                nullable.add(rule.lhs)
                changed = True
    return frozenset(nullable)


def _productive(grammar: Grammar) -> set[str]:
    productive: set[str] = set()
    changed = True
    while changed:
        changed = False
        for rule in grammar.user_rules:
            if rule.lhs in productive:
                continue
            if all(s.kind == "terminal" or s.value in productive for s in rule.rhs):
                productive.add(rule.lhs)
                changed = True
    return productive


def _reachable(grammar: Grammar) -> set[str]:
    reachable = {grammar.start}
    stack = [grammar.start]
    while stack:
        for rule in grammar.by_lhs.get(stack.pop(), []):
            for s in rule.rhs:
                if s.kind == "nonterminal" and s.value not in reachable:
                    reachable.add(s.value)
                    stack.append(s.value)
    return reachable


def find_cycles(grammar: Grammar) -> list[list[str]]:
    """Cycles A ⇒+ A (through unit rules and nullable context). Such grammars give infinitely
    many parse trees for some sentences, so the Lab rejects them."""
    edges: dict[str, set[str]] = defaultdict(set)
    for rule in grammar.user_rules:
        for i, s in enumerate(rule.rhs):
            if s.kind != "nonterminal":
                continue
            others = rule.rhs[:i] + rule.rhs[i + 1 :]
            if all(o.kind == "nonterminal" and o.value in grammar.nullable for o in others):
                edges[rule.lhs].add(s.value)

    cycles: list[list[str]] = []
    state: dict[str, int] = {}  # 1 = on stack, 2 = done
    path: list[str] = []

    def visit(node: str) -> None:
        state[node] = 1
        path.append(node)
        for nxt in sorted(edges.get(node, ())):
            if state.get(nxt) == 1:
                cycles.append([*path[path.index(nxt) :], nxt])
            elif nxt not in state:
                visit(nxt)
        path.pop()
        state[node] = 2

    for node in sorted(edges):
        if node not in state:
            visit(node)
    return cycles


def analyze_grammar(grammar: Grammar) -> list[Diagnostic]:
    problems: list[Diagnostic] = []
    if len(grammar.user_rules) > MAX_RULES:
        problems.append(
            Diagnostic(
                "error",
                "too_many_rules",
                f"The Lab accepts at most {MAX_RULES} rules ({len(grammar.user_rules)} given).",
            )
        )
    defined = set(grammar.by_lhs)
    for rule in grammar.user_rules:
        if len(rule.rhs) > MAX_RHS:
            problems.append(
                Diagnostic(
                    "error",
                    "rule_too_long",
                    f"Right-hand sides are limited to {MAX_RHS} symbols.",
                    rule.line,
                )
            )
        for s in (Symbol("nonterminal", rule.lhs), *rule.rhs):
            if len(s.value) > MAX_SYMBOL_LENGTH:
                problems.append(
                    Diagnostic(
                        "error",
                        "symbol_too_long",
                        f"Symbol “{s.value[:16]}…” is too long.",
                        rule.line,
                    )
                )
        for s in rule.rhs:
            if s.kind == "nonterminal" and s.value not in defined:
                problems.append(
                    Diagnostic(
                        "error",
                        "undefined_symbol",
                        f"{s.value} is used in {rule.text()} but has no rules. "
                        f"Define it, or quote it if it is a word.",
                        rule.line,
                    )
                )
    if any(p.severity == "error" for p in problems):
        return problems

    for cycle in find_cycles(grammar):
        line = next((r.line for r in grammar.by_lhs.get(cycle[0], [])), None)
        problems.append(
            Diagnostic(
                "error",
                "cyclic_grammar",
                f"{' ⇒ '.join(cycle)}: a symbol can derive itself, so some sentences would have "
                f"infinitely many parse trees.",
                line,
            )
        )

    productive = _productive(grammar)
    if grammar.start not in productive:
        problems.append(
            Diagnostic(
                "error",
                "start_unproductive",
                f"The start symbol {grammar.start} cannot derive any sentence.",
            )
        )
    for symbol in grammar.nonterminals:
        if symbol not in productive and symbol != grammar.start:
            line = grammar.by_lhs[symbol][0].line
            problems.append(
                Diagnostic(
                    "warning",
                    "unproductive_symbol",
                    f"{symbol} can never derive a complete phrase "
                    "(every rule needs itself or another such symbol).",
                    line,
                )
            )
    reachable = _reachable(grammar)
    for symbol in grammar.nonterminals:
        if symbol not in reachable:
            line = grammar.by_lhs[symbol][0].line
            problems.append(
                Diagnostic(
                    "warning",
                    "unreachable_symbol",
                    f"{symbol} is never used starting from {grammar.start}.",
                    line,
                )
            )
    return problems


def compile_grammar(text: str) -> tuple[Grammar | None, list[Diagnostic]]:
    """Parse and validate. Returns a usable grammar only if there are no errors."""
    grammar, problems = parse_grammar(text)
    if grammar is None:
        return None, problems
    problems = problems + analyze_grammar(grammar)
    if any(p.severity == "error" for p in problems):
        return None, problems
    return grammar, problems


# ---------------------------------------------------------------------- tokenization

_PUNCTUATION = re.compile(r"""([.,!?;:"()])""")


def tokenize(sentence: str) -> list[str]:
    """Split on whitespace; punctuation marks become separate tokens."""
    return _PUNCTUATION.sub(r" \1 ", sentence).split()


def matches(terminal: str, token: str) -> bool:
    """Grammar words match case-insensitively (so sentence-initial capitals still match)."""
    return terminal.casefold() == token.casefold()
