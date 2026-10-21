"""Earley parser with an execution trace and a shared packed parse forest.

References: Earley (1970); Aycock & Horspool (2002) for nullable symbols; Scott (2008) for
building parse forests from Earley recognisers (see docs/research/parsing-strategies.md).

Design notes
------------
* Items are ``(rule, dot, origin)``; ``chart[k]`` holds the items ending at position ``k`` in
  insertion order. Rule 0 is the augmented rule ``γ → start``; the input is accepted iff
  ``γ → start •`` with origin 0 is in ``chart[n]``.
* **Nullable symbols** (Aycock & Horspool): when the predictor meets a nullable nonterminal B
  it also advances the dot over B immediately. All empty-span derivations are therefore
  represented by these ε-links, and the completer ignores completed items with an empty span,
  so no derivation is counted twice.
* **Forest**: every advanced item keeps *derivation links* ``(previous item, child)`` where the
  child is a scanned token, a completed item, or an ε-derivation of a nullable symbol. These
  links form a shared packed parse forest. Trees are counted exactly by dynamic programming and
  enumerated lazily up to a cap. (Earley's original tree-recovery scheme can produce spurious
  trees; links per item avoid that.)
* **Trace**: every operation is recorded as an event, including scans that fail and attempts
  that add nothing new. The UI replays these events; it never simulates the algorithm.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import islice
from typing import Literal

from syntaxlab_api.grammar.grammar import Grammar, matches

EventKind = Literal[
    "init", "predict", "nullable", "scan", "scan_fail", "complete", "accept", "reject"
]

ItemKey = tuple[int, int, int, int]  # rule, dot, origin, end


@dataclass(frozen=True)
class Child:
    kind: Literal["token", "item", "empty"]
    token: int | None = None  # position of the scanned token
    item: ItemKey | None = None  # completed item for a nonterminal
    symbol: str | None = None  # nullable nonterminal derived as ε


@dataclass(frozen=True)
class Link:
    previous: ItemKey | None  # item with the dot one position to the left (None when dot was 0)
    child: Child


@dataclass(frozen=True)
class ItemRef:
    set: int
    index: int


@dataclass
class ChartItem:
    rule: int
    dot: int
    origin: int
    end: int
    step: int  # event at which the item was first added
    links: list[Link] = field(default_factory=list)

    @property
    def key(self) -> ItemKey:
        return (self.rule, self.dot, self.origin, self.end)


@dataclass(frozen=True)
class Event:
    step: int
    kind: EventKind
    set: int
    item: ItemRef | None  # item added (or that would have been added)
    added: bool
    cause: ItemRef | None  # item being processed when the event happened
    completed: ItemRef | None = None  # for "complete": the finished constituent
    symbol: str | None = None  # predicted / skipped / expected symbol
    token: int | None = None  # input position involved in a scan
    rule: int | None = None  # rule of a predicted item


@dataclass
class Tree:
    symbol: str
    start: int
    end: int
    rule: int | None = None  # None for terminals
    token: int | None = None  # set on terminals
    children: list[Tree] = field(default_factory=list)


@dataclass
class EarleyResult:
    tokens: list[str]
    chart: list[list[ChartItem]]
    events: list[Event]
    accepted: bool
    events_truncated: bool


class Earley:
    def __init__(self, grammar: Grammar, *, max_events: int = 20_000) -> None:
        self.grammar = grammar
        self.max_events = max_events

    # ------------------------------------------------------------------ recognition

    def parse(self, tokens: list[str]) -> EarleyResult:
        g = self.grammar
        n = len(tokens)
        chart: list[list[ChartItem]] = [[] for _ in range(n + 1)]
        index: list[dict[tuple[int, int, int], int]] = [{} for _ in range(n + 1)]
        events: list[Event] = []
        truncated = False

        def record(event_kwargs: dict[str, object]) -> int:
            nonlocal truncated
            step = len(events) if not truncated else -1
            if not truncated:
                if len(events) >= self.max_events:
                    truncated = True
                    return -1
                events.append(Event(step=len(events), **event_kwargs))  # type: ignore[arg-type]
            return step

        def ref(k: int, item: tuple[int, int, int]) -> ItemRef:
            return ItemRef(k, index[k][item])

        def add(
            k: int,
            item: tuple[int, int, int],
            link: Link | None,
            event: dict[str, object],
        ) -> None:
            existing = index[k].get(item)
            if existing is None:
                index[k][item] = len(chart[k])
                step = len(events)
                chart[k].append(ChartItem(*item, end=k, step=step))
                existing = index[k][item]
                added = True
            else:
                added = False
            if link is not None and link not in chart[k][existing].links:
                chart[k][existing].links.append(link)
            record({**event, "set": k, "item": ItemRef(k, existing), "added": added})

        add(0, (0, 0, 0), None, {"kind": "init", "cause": None, "rule": 0})

        for k in range(n + 1):
            i = 0
            while i < len(chart[k]):
                current = chart[k][i]
                i += 1
                rule = g.rules[current.rule]
                here = ItemRef(k, i - 1)
                key = current.key
                if current.dot < len(rule.rhs):
                    symbol = rule.rhs[current.dot]
                    if symbol.kind == "nonterminal":
                        for alt in g.by_lhs.get(symbol.value, []):
                            add(
                                k,
                                (alt.index, 0, k),
                                None,
                                {
                                    "kind": "predict",
                                    "cause": here,
                                    "symbol": symbol.value,
                                    "rule": alt.index,
                                },
                            )
                        if symbol.value in g.nullable:
                            add(
                                k,
                                (current.rule, current.dot + 1, current.origin),
                                Link(key, Child("empty", symbol=symbol.value)),
                                {"kind": "nullable", "cause": here, "symbol": symbol.value},
                            )
                    elif k < n and matches(symbol.value, tokens[k]):
                        add(
                            k + 1,
                            (current.rule, current.dot + 1, current.origin),
                            Link(key, Child("token", token=k)),
                            {"kind": "scan", "cause": here, "symbol": symbol.value, "token": k},
                        )
                    else:
                        record(
                            {
                                "kind": "scan_fail",
                                "set": k,
                                "item": None,
                                "added": False,
                                "cause": here,
                                "symbol": symbol.value,
                                "token": k if k < n else None,
                            }
                        )
                elif current.origin < k:  # empty-span completions are covered by ε-links
                    for waiting in list(chart[current.origin]):
                        w_rule = g.rules[waiting.rule]
                        if (
                            waiting.dot < len(w_rule.rhs)
                            and w_rule.rhs[waiting.dot].kind == "nonterminal"
                            and w_rule.rhs[waiting.dot].value == rule.lhs
                        ):
                            add(
                                k,
                                (waiting.rule, waiting.dot + 1, waiting.origin),
                                Link(waiting.key, Child("item", item=key)),
                                {
                                    "kind": "complete",
                                    "cause": ref(
                                        current.origin, (waiting.rule, waiting.dot, waiting.origin)
                                    ),
                                    "completed": here,
                                    "symbol": rule.lhs,
                                },
                            )

        accepted = (0, 1, 0) in index[n]
        record(
            {
                "kind": "accept" if accepted else "reject",
                "set": n,
                "item": ref(n, (0, 1, 0)) if accepted else None,
                "added": False,
                "cause": None,
            }
        )
        return EarleyResult(tokens, chart, events, accepted, truncated)


# ---------------------------------------------------------------------- forest


class Forest:
    """Counting and enumerating the parse trees encoded by an Earley chart's links."""

    def __init__(self, grammar: Grammar, result: EarleyResult) -> None:
        self.grammar = grammar
        self.result = result
        self.items: dict[ItemKey, ChartItem] = {
            item.key: item for column in result.chart for item in column
        }
        self._count: dict[ItemKey, int] = {}
        self._empty_count: dict[str, int] = {}

    @property
    def root(self) -> ItemKey | None:
        n = len(self.result.tokens)
        key = (0, 1, 0, n)
        return key if key in self.items else None

    # ------------------------------------------------------------------ counting

    def empty_count(self, symbol: str) -> int:
        if symbol not in self._empty_count:
            total = 0
            for rule in self.grammar.by_lhs.get(symbol, []):
                if all(
                    s.kind == "nonterminal" and s.value in self.grammar.nullable for s in rule.rhs
                ):
                    product = 1
                    for s in rule.rhs:
                        product *= self.empty_count(s.value)
                    total += product
            self._empty_count[symbol] = total
        return self._empty_count[symbol]

    def count(self, key: ItemKey) -> int:
        """Number of distinct derivations of an item (exact; may be very large)."""
        if key in self._count:
            return self._count[key]
        item = self.items[key]
        if item.dot == 0:
            total = 1
        else:
            total = 0
            for link in item.links:
                previous = self.count(link.previous) if link.previous is not None else 1
                total += previous * self._child_count(link.child)
        self._count[key] = total
        return total

    def _child_count(self, child: Child) -> int:
        if child.kind == "token":
            return 1
        if child.kind == "empty":
            assert child.symbol is not None
            return self.empty_count(child.symbol)
        assert child.item is not None
        return self.count(child.item)

    def tree_count(self) -> int:
        root = self.root
        return self.count(root) if root is not None else 0

    # ------------------------------------------------------------------ enumeration

    def trees(self, limit: int) -> list[Tree]:
        root = self.root
        if root is None:
            return []
        # γ → S • : its single child is the tree for the start symbol (placed at position 0,
        # which matters when the whole input is empty and S derives ε).
        return [_place_empty(children, 0)[0] for children in islice(self._sequences(root), limit)]

    def _sequences(self, key: ItemKey) -> Iterator[list[Tree]]:
        """All child sequences for an item's right-hand side up to its dot."""
        item = self.items[key]
        if item.dot == 0:
            yield []
            return
        for link in item.links:
            previous = self._sequences(link.previous) if link.previous is not None else iter([[]])
            for prefix in previous:
                for child in self._child_trees(link.child):
                    yield [*prefix, child]

    def _child_trees(self, child: Child) -> Iterator[Tree]:
        if child.kind == "token":
            assert child.token is not None
            word = self.result.tokens[child.token]
            yield Tree(symbol=word, start=child.token, end=child.token + 1, token=child.token)
        elif child.kind == "empty":
            assert child.symbol is not None
            # The position is filled in by the parent (empty trees have no tokens).
            yield from self._empty_trees(child.symbol)
        else:
            assert child.item is not None
            rule, _, origin, end = child.item
            for sequence in self._sequences(child.item):
                yield Tree(
                    symbol=self.grammar.rules[rule].lhs,
                    start=origin,
                    end=end,
                    rule=rule,
                    children=_place_empty(sequence, origin),
                )

    def _empty_trees(self, symbol: str) -> Iterator[Tree]:
        for rule in self.grammar.by_lhs.get(symbol, []):
            if all(s.kind == "nonterminal" and s.value in self.grammar.nullable for s in rule.rhs):
                for children in _product([self._empty_trees(s.value) for s in rule.rhs]):
                    yield Tree(symbol=symbol, start=-1, end=-1, rule=rule.index, children=children)


def _product(generators: list[Iterator[Tree]]) -> Iterator[list[Tree]]:
    """Cartesian product of lazily generated subtrees (materialized per position)."""
    pools = [list(g) for g in generators]

    def go(i: int) -> Iterator[list[Tree]]:
        if i == len(pools):
            yield []
            return
        for head in pools[i]:
            for tail in go(i + 1):
                yield [head, *tail]

    yield from go(0)


def _place_empty(children: list[Tree], start: int) -> list[Tree]:
    """Give empty subtrees (start = -1) the position where they occur in the sentence."""
    placed: list[Tree] = []
    position = start
    for child in children:
        if child.start < 0:
            child = _with_position(child, position)
        placed.append(child)
        position = child.end
    return placed


def _with_position(tree: Tree, position: int) -> Tree:
    return Tree(
        symbol=tree.symbol,
        start=position,
        end=position,
        rule=tree.rule,
        token=tree.token,
        children=[_with_position(c, position) for c in tree.children],
    )
