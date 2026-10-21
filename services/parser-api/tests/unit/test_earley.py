"""Correctness of the Earley parser, its trace, and its parse forest.

The central check compares Earley's trees with an *independent oracle*: a brute-force,
span-based enumeration of all derivations written separately below. On every tested sentence
the two must produce exactly the same set of trees.
"""

from __future__ import annotations

import itertools
import random
from functools import cache
from pathlib import Path

import pytest

from syntaxlab_api.grammar.earley import Earley, EarleyResult, Forest, Tree
from syntaxlab_api.grammar.grammar import Grammar, compile_grammar, matches, tokenize
from syntaxlab_api.grammar.presets import load_presets
from syntaxlab_api.settings import SERVICE_ROOT

PRESETS = load_presets(SERVICE_ROOT / "data" / "grammars")

EPSILON_GRAMMARS = {
    # Aycock & Horspool (2002): many ways to place the a's among four nullable slots.
    "four-slots": 'S -> A A A A\nA -> "a" | E\nE -> ε',
    # Nullable symbol before a recursive call (hidden left recursion).
    "hidden-left": 'S -> A S "b" | "a"\nA -> ε',
    # Nullable chains and optional elements on both sides.
    "chains": 'S -> X "m" Y\nX -> Y Y | "x"\nY -> Z | "y"\nZ -> ε',
    # Right recursion with an empty base case.
    "right": 'L -> "a" L | ε',
}


def compile_ok(text: str) -> Grammar:
    grammar, problems = compile_grammar(text)
    assert grammar is not None, problems
    return grammar


def run(grammar: Grammar, sentence: str | list[str]) -> tuple[EarleyResult, Forest]:
    tokens = tokenize(sentence) if isinstance(sentence, str) else sentence
    result = Earley(grammar).parse(tokens)
    return result, Forest(grammar, result)


# ---------------------------------------------------------------------- oracle

Canon = tuple[object, ...]


def canonical(tree: Tree) -> Canon:
    if tree.token is not None:
        return ("t", tree.token)
    return (
        tree.symbol,
        tree.rule,
        tree.start,
        tree.end,
        tuple(canonical(c) for c in tree.children),
    )


def oracle_nullable(grammar: Grammar) -> set[str]:
    """Nullable nonterminals, computed independently of the implementation."""
    nullable: set[str] = set()
    while True:
        new = {
            r.lhs
            for r in grammar.user_rules
            if all(s.kind == "nonterminal" and s.value in nullable for s in r.rhs)
        }
        if new <= nullable:
            return nullable
        nullable |= new


def oracle(grammar: Grammar, tokens: list[str]) -> set[Canon]:
    """All derivation trees of the start symbol over the whole input, by exhaustive search over
    spans. Independent of the Earley implementation; exponential, so only for small inputs."""
    nullable = oracle_nullable(grammar)

    def rest_nullable(rule_index: int, pos: int) -> bool:
        return all(
            s.kind == "nonterminal" and s.value in nullable
            for s in grammar.rules[rule_index].rhs[pos:]
        )

    @cache
    def derive(symbol: str, i: int, j: int) -> tuple[Canon, ...]:
        out: list[Canon] = []
        for rule in grammar.by_lhs.get(symbol, []):
            for seq in sequence(rule.index, 0, i, j):
                out.append((symbol, rule.index, i, j, seq))
        return tuple(out)

    @cache
    def sequence(rule_index: int, pos: int, i: int, j: int) -> tuple[tuple[Canon, ...], ...]:
        rhs = grammar.rules[rule_index].rhs
        if pos == len(rhs):
            return ((),) if i == j else ()
        sym = rhs[pos]
        out: list[tuple[Canon, ...]] = []
        if sym.kind == "terminal":
            if i < j and matches(sym.value, tokens[i]):
                out.extend((("t", i), *rest) for rest in sequence(rule_index, pos + 1, i + 1, j))
            return tuple(out)
        for k in range(i, j + 1):
            # Empty-span parts are only explored when they can be empty. With an acyclic
            # grammar this guarantees progress, so left and right recursion both terminate.
            if k == i and sym.value not in nullable:
                continue
            if k == j and not rest_nullable(rule_index, pos + 1):
                continue
            heads = derive(sym.value, i, k)
            if not heads:
                continue
            for head in heads:
                out.extend((head, *rest) for rest in sequence(rule_index, pos + 1, k, j))
        return tuple(out)

    return set(derive(grammar.start, 0, len(tokens)))


def assert_matches_oracle(grammar: Grammar, tokens: list[str]) -> None:
    result, forest = run(grammar, tokens)
    expected = oracle(grammar, tokens)
    trees = forest.trees(limit=10_000)
    got = [canonical(t) for t in trees]
    assert len(got) == len(set(got)), "Earley produced duplicate trees"
    assert set(got) == expected, tokens
    assert forest.tree_count() == len(expected)
    assert result.accepted == bool(expected)


def sample_sentence(grammar: Grammar, rng: random.Random, max_depth: int = 6) -> list[str]:
    def expand(symbol: str, depth: int) -> list[str]:
        rules = grammar.by_lhs[symbol]
        if depth >= max_depth:  # prefer short rules near the depth limit
            rules = sorted(rules, key=lambda r: len(r.rhs))[:1]
        rule = rng.choice(rules)
        words: list[str] = []
        for s in rule.rhs:
            words.extend([s.value] if s.kind == "terminal" else expand(s.value, depth + 1))
        return words

    return expand(grammar.start, 0)


# ---------------------------------------------------------------------- tests


@pytest.mark.parametrize("preset_id", sorted(PRESETS))
def test_preset_examples_behave_as_documented(preset_id: str) -> None:
    preset = PRESETS[preset_id]
    grammar = compile_ok(preset.grammar)
    for example in preset.examples:
        result, forest = run(grammar, example.text)
        assert result.accepted == example.expect.accepted, example.text
        assert forest.tree_count() == example.expect.parses, example.text


@pytest.mark.parametrize("preset_id", sorted(PRESETS))
def test_presets_agree_with_oracle_on_random_sentences(preset_id: str) -> None:
    grammar = compile_ok(PRESETS[preset_id].grammar)
    rng = random.Random(preset_id)
    vocabulary = grammar.terminals
    sentences: list[list[str]] = []
    for _ in range(40):
        words = sample_sentence(grammar, rng)
        if 0 < len(words) <= 9:
            sentences.append(words)
            # A mutated copy is usually ungrammatical: tests rejection too.
            mutated = list(words)
            mutated[rng.randrange(len(mutated))] = rng.choice(vocabulary)
            sentences.append(mutated)
    assert len(sentences) >= 20
    outcomes = set()
    for words in sentences:
        assert_matches_oracle(grammar, words)
        outcomes.add(bool(oracle(grammar, words)))
    assert outcomes == {True, False}, "sample must include accepted and rejected sentences"


@pytest.mark.parametrize("name", sorted(EPSILON_GRAMMARS))
def test_empty_rules_exhaustively_against_oracle(name: str) -> None:
    grammar = compile_ok(EPSILON_GRAMMARS[name])
    for length in range(0, 5):
        for words in itertools.product(grammar.terminals, repeat=length):
            assert_matches_oracle(grammar, list(words))


def test_four_nullable_slots_count() -> None:
    # Two a's in four slots: C(4, 2) = 6 placements.
    _, forest = run(compile_ok(EPSILON_GRAMMARS["four-slots"]), ["a", "a"])
    assert forest.tree_count() == 6


CATALAN = [1, 1, 2, 5, 14, 42, 132]


@pytest.mark.parametrize("operators", range(1, 7))
def test_ambiguity_grows_as_catalan_numbers_arithmetic(operators: int) -> None:
    grammar = compile_ok(PRESETS["arithmetic"].grammar)
    sentence = " + ".join(["n"] * (operators + 1))
    _, forest = run(grammar, sentence)
    assert forest.tree_count() == CATALAN[operators]


@pytest.mark.parametrize(("pps", "parses"), [(1, 2), (2, 5), (3, 14), (4, 42)])
def test_pp_attachment_ambiguity_is_catalan(pps: int, parses: int) -> None:
    grammar = compile_ok(PRESETS["pp-attachment"].grammar)
    phrases = ["with a telescope", "on the hill", "in the park", "with a book"][:pps]
    _, forest = run(grammar, "I saw the man " + " ".join(phrases))
    assert forest.tree_count() == parses


def test_tree_enumeration_is_capped_but_count_is_exact() -> None:
    grammar = compile_ok(PRESETS["arithmetic"].grammar)
    _, forest = run(grammar, " + ".join(["n"] * 11))  # 10 operators: C10 = 16796
    assert forest.tree_count() == 16796
    trees = forest.trees(limit=20)
    assert len(trees) == 20
    assert len({canonical(t) for t in trees}) == 20


def test_case_insensitive_words_and_punctuation_tokens() -> None:
    grammar = compile_ok('S -> "i" V "."\nV -> "agree"')
    assert tokenize("I agree.") == ["I", "agree", "."]
    result, _ = run(grammar, "I agree.")
    assert result.accepted


def test_trees_record_rules_spans_and_tokens() -> None:
    grammar = compile_ok(PRESETS["pp-attachment"].grammar)
    _, forest = run(grammar, "the student reads a book")
    (tree,) = forest.trees(limit=5)
    assert (tree.symbol, tree.start, tree.end) == ("S", 0, 5)
    np, vp = tree.children
    assert (np.symbol, np.start, np.end) == ("NP", 0, 2)
    assert (vp.symbol, vp.start, vp.end) == ("VP", 2, 5)
    leaves: list[Tree] = []

    def collect(t: Tree) -> None:
        if t.token is not None:
            leaves.append(t)
        for c in t.children:
            collect(c)

    collect(tree)
    assert [(leaf.symbol, leaf.token) for leaf in leaves] == [
        ("the", 0),
        ("student", 1),
        ("reads", 2),
        ("a", 3),
        ("book", 4),
    ]
    assert grammar.rules[tree.rule or 0].text() == "S → NP VP"


def test_empty_constituents_are_placed_at_their_position() -> None:
    grammar = compile_ok(PRESETS["optional-elements"].grammar)
    _, forest = run(grammar, "dogs sleep")
    (tree,) = forest.trees(limit=5)
    np = tree.children[0]
    det, adjp, n = np.children
    assert (det.symbol, det.start, det.end, det.children) == ("Det", 0, 0, [])
    assert (adjp.symbol, adjp.start, adjp.end) == ("AdjP", 0, 0)
    assert (n.symbol, n.start, n.end) == ("N", 0, 1)


class TestTrace:
    grammar = compile_ok(PRESETS["pp-attachment"].grammar)

    def test_replaying_events_rebuilds_the_chart(self) -> None:
        result, _ = run(self.grammar, "I saw the man with a telescope")
        assert not result.events_truncated
        rebuilt: list[list[tuple[int, int, int]]] = [[] for _ in result.chart]
        for event in result.events:
            if event.added:
                assert event.item is not None
                assert event.item.index == len(rebuilt[event.item.set])  # insertion order
                item = result.chart[event.item.set][event.item.index]
                assert item.step == event.step
                rebuilt[event.item.set].append((item.rule, item.dot, item.origin))
        assert rebuilt == [[(i.rule, i.dot, i.origin) for i in column] for column in result.chart]

    def test_events_are_consistent_with_the_algorithm(self) -> None:
        result, _ = run(self.grammar, "I saw the man with a telescope")
        tokens = result.tokens
        rules = self.grammar.rules
        for event in result.events:
            assert event.step == result.events.index(event)
            if event.kind == "scan":
                assert event.token is not None
                assert event.symbol is not None
                assert matches(event.symbol, tokens[event.token])
                assert event.set == event.token + 1
            if event.kind == "scan_fail" and event.token is not None:
                assert event.symbol is not None
                assert not matches(event.symbol, tokens[event.token])
            if event.kind == "complete":
                assert event.completed is not None
                assert event.cause is not None
                done = result.chart[event.completed.set][event.completed.index]
                waiting = result.chart[event.cause.set][event.cause.index]
                assert done.dot == len(rules[done.rule].rhs)
                expected = rules[waiting.rule].rhs[waiting.dot]
                assert (expected.kind, expected.value) == ("nonterminal", rules[done.rule].lhs)
            if event.kind == "predict":
                assert event.rule is not None
                assert event.cause is not None
                cause = result.chart[event.cause.set][event.cause.index]
                assert rules[cause.rule].rhs[cause.dot].value == rules[event.rule].lhs
        assert result.events[0].kind == "init"
        assert result.events[-1].kind == "accept"

    def test_rejection_is_recorded_with_failed_scans(self) -> None:
        result, forest = run(self.grammar, "I saw the man with")
        assert result.events[-1].kind == "reject"
        assert forest.tree_count() == 0
        # At the end of the input every expected word is a failed scan with no token.
        assert any(e.kind == "scan_fail" and e.token is None for e in result.events)

    def test_trace_can_be_truncated_without_affecting_the_result(self) -> None:
        full = Earley(self.grammar).parse(tokenize("I saw the man with a telescope"))
        short = Earley(self.grammar, max_events=10).parse(
            tokenize("I saw the man with a telescope")
        )
        assert short.events_truncated
        assert len(short.events) == 10
        assert short.accepted == full.accepted
        assert [len(c) for c in short.chart] == [len(c) for c in full.chart]


def test_presets_directory_exists() -> None:
    assert Path(SERVICE_ROOT / "data" / "grammars").is_dir()
    assert {"pp-attachment", "coordination", "optional-elements", "arithmetic"} <= set(PRESETS)
