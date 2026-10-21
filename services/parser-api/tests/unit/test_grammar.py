from __future__ import annotations

import pytest

from syntaxlab_api.grammar.grammar import (
    AUGMENTED_START,
    MAX_RULES,
    compile_grammar,
    find_cycles,
    parse_grammar,
    tokenize,
)


def codes(text: str) -> list[tuple[str, str, int | None]]:
    _, problems = compile_grammar(text)
    return [(p.severity, p.code, p.line) for p in problems]


class TestNotation:
    def test_rules_alternatives_and_start_symbol(self) -> None:
        grammar, problems = parse_grammar(
            'S -> NP VP\nNP -> Det N | "she"\nDet -> "the"\nN -> "cat"\nVP -> "sleeps"'
        )
        assert grammar is not None
        assert problems == []
        assert grammar.start == "S"
        assert grammar.rules[0].lhs == AUGMENTED_START
        assert [r.text() for r in grammar.user_rules] == [
            "S → NP VP",
            "NP → Det N",
            'NP → "she"',
            'Det → "the"',
            'N → "cat"',
            'VP → "sleeps"',
        ]
        assert grammar.terminals == ["she", "the", "cat", "sleeps"]
        assert [r.line for r in grammar.user_rules] == [1, 2, 2, 3, 4, 5]

    @pytest.mark.parametrize("empty", ["ε", "ϵ", '""', "''"])
    def test_epsilon_forms(self, empty: str) -> None:
        grammar, problems = parse_grammar(f'S -> A "x"\nA -> {empty}')
        assert grammar is not None, problems
        assert grammar.by_lhs["A"][0].rhs == ()
        assert grammar.nullable == {"A"}

    def test_unicode_arrow_continuation_lines_and_comments(self) -> None:
        text = '# a comment\nS → "a" # trailing\n  | "#"\n  | B\nB -> "b"'
        grammar, problems = parse_grammar(text)
        assert grammar is not None, problems
        assert [r.text() for r in grammar.by_lhs["S"]] == ['S → "a"', 'S → "#"', "S → B"]

    def test_primes_in_nonterminals_do_not_open_quotes(self) -> None:
        grammar, problems = parse_grammar(
            'NP -> Det N\'  # X-bar style, isn\'t it\nN\' -> "cat"\nDet -> "a"'
        )
        assert grammar is not None, problems
        assert "N'" in grammar.nonterminals

    def test_single_quoted_terminals(self) -> None:
        grammar, _ = parse_grammar("S -> 'hello'")
        assert grammar is not None
        assert grammar.terminals == ["hello"]

    @pytest.mark.parametrize(
        ("text", "code", "line"),
        [
            ("S NP VP", "missing_arrow", 1),
            ('S -> "a"\n"x" -> "b"', "bad_lhs", 2),
            ("S -> NP ε", "epsilon_not_alone", 1),
            ('S -> "a" ""', "empty_terminal", 1),
            ("S -> NP-VP", "bad_symbol", 1),
            ('S -> "two words"', "bad_symbol", 1),
            ("| A", "dangling_alternative", 1),
            ('S -> "a" |', "empty_alternative", 1),
        ],
    )
    def test_syntax_errors_have_codes_and_lines(self, text: str, code: str, line: int) -> None:
        grammar, problems = parse_grammar(text)
        assert grammar is None
        assert (code, line) in [(p.code, p.line) for p in problems]

    def test_empty_grammar(self) -> None:
        assert parse_grammar("# nothing\n")[1][0].code == "no_rules"

    def test_duplicate_rules_are_dropped_with_warning(self) -> None:
        grammar, problems = parse_grammar('S -> "a"\nS -> "a"')
        assert grammar is not None
        assert len(grammar.user_rules) == 1
        assert [(p.severity, p.code, p.line) for p in problems] == [
            ("warning", "duplicate_rule", 2)
        ]


class TestValidation:
    def test_valid_grammar_has_no_problems(self) -> None:
        assert codes('S -> NP "v"\nNP -> "n"') == []

    def test_undefined_symbol(self) -> None:
        assert ("error", "undefined_symbol", 1) in codes('S -> NP VP\nNP -> "n"')

    def test_direct_cycle(self) -> None:
        assert ("error", "cyclic_grammar", 2) in codes('S -> A\nA -> A | "a"')

    def test_indirect_cycle_through_nullable_context(self) -> None:
        # A ⇒ B C ⇒ B (C is empty) ⇒ A : infinitely many trees
        grammar, _ = parse_grammar('A -> B C | "a"\nB -> A\nC -> ε | "c"')
        assert grammar is not None
        cycles = find_cycles(grammar)
        assert cycles
        assert set(cycles[0]) == {"A", "B"}
        assert any(c[1] == "cyclic_grammar" for c in codes('A -> B C | "a"\nB -> A\nC -> ε | "c"'))

    def test_left_recursion_is_not_a_cycle(self) -> None:
        assert codes('NP -> NP PP | "n"\nPP -> "p" NP') == []

    def test_unproductive_and_unreachable_are_warnings(self) -> None:
        problems = codes('S -> "a" | X\nX -> X "b"\nY -> "c"')
        assert ("warning", "unproductive_symbol", 2) in problems
        assert ("warning", "unreachable_symbol", 3) in problems
        assert compile_grammar('S -> "a" | X\nX -> X "b"\nY -> "c"')[0] is not None

    def test_unproductive_start_is_an_error(self) -> None:
        assert ("error", "start_unproductive", None) in codes('S -> S "a"')

    def test_size_limits(self) -> None:
        many = "\n".join(f'S -> "w{i}"' for i in range(MAX_RULES + 1))
        assert ("error", "too_many_rules", None) in codes(many)
        long_rhs = "S -> " + " ".join(['"a"'] * 13)
        assert ("error", "rule_too_long", 1) in codes(long_rhs)


def test_tokenize_splits_punctuation() -> None:
    assert tokenize("Hello, world!  (yes)") == ["Hello", ",", "world", "!", "(", "yes", ")"]
    assert tokenize("   ") == []
