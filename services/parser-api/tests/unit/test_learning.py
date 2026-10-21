"""Exercise bank integrity and answer checking."""

from __future__ import annotations

import random
from typing import ClassVar

import pytest

from syntaxlab_api import errors
from syntaxlab_api.grammar.earley import Earley, Forest
from syntaxlab_api.grammar.grammar import compile_grammar, tokenize
from syntaxlab_api.grammar.presets import load_presets
from syntaxlab_api.learning.checking import (
    _prune_empty,
    check_constituency,
    check_dependency,
    check_pos,
    spans_of,
)
from syntaxlab_api.learning.exercises import (
    ConstituencyExercise,
    DependencyExercise,
    PosExercise,
    load_exercises,
)
from syntaxlab_api.schemas.learning import (
    ConstituencyAnswer,
    ConstituentIn,
    DependencyAnswer,
    DependencyAnswerArc,
    PosAnswer,
)
from syntaxlab_api.settings import SERVICE_ROOT

PRESETS = load_presets(SERVICE_ROOT / "data" / "grammars")
EXERCISES = load_exercises(SERVICE_ROOT / "data" / "exercises", PRESETS)


def answer(spans: list[tuple[str, int, int]]) -> ConstituencyAnswer:
    return ConstituencyAnswer(
        kind="constituency",
        constituents=[ConstituentIn(label=label, start=s, end=e) for label, s, e in spans],
    )


def exercise(grammar: str, sentence: str) -> ConstituencyExercise:
    return ConstituencyExercise(
        kind="constituency", id="test", title="t", difficulty=1, grammar=grammar, sentence=sentence
    )


def all_parse_spans(grammar_text: str, sentence: str) -> list[list[tuple[str, int, int]]]:
    grammar, _ = compile_grammar(grammar_text)
    assert grammar is not None
    forest = Forest(grammar, Earley(grammar).parse(tokenize(sentence)))
    out = []
    for tree in forest.trees(limit=100):
        pruned = _prune_empty(tree)
        assert pruned is not None
        out.append(spans_of(pruned))
    return out


class TestBank:
    def test_kinds_and_counts(self) -> None:
        kinds = [e.kind for e in EXERCISES.values()]
        assert kinds.count("pos") == 8
        assert kinds.count("dependency") == 8
        assert kinds.count("constituency") >= 4
        assert kinds == sorted(kinds, key=["pos", "dependency", "constituency"].index)

    def test_ud_exercises_carry_their_source(self) -> None:
        for e in EXERCISES.values():
            if isinstance(e, PosExercise | DependencyExercise):
                assert e.source.treebank == "UD_English-EWT"
                assert e.source.license == "CC BY-SA 4.0"
                assert 5 <= len(e.tokens) <= 10


class TestPos:
    ex = next(e for e in EXERCISES.values() if isinstance(e, PosExercise))

    def test_all_correct(self) -> None:
        fb = check_pos(self.ex, PosAnswer(kind="pos", tags=[t.upos for t in self.ex.tokens]))
        assert (fb.correct, fb.total) == (len(self.ex.tokens), len(self.ex.tokens))

    def test_wrong_and_unanswered(self) -> None:
        tags: list[str | None] = [t.upos for t in self.ex.tokens]
        tags[0] = "X" if self.ex.tokens[0].upos != "X" else "NOUN"
        tags[1] = None
        fb = check_pos(self.ex, PosAnswer(kind="pos", tags=tags))
        assert [i.status for i in fb.items[:2]] == ["incorrect", "unanswered"]
        assert fb.items[0].expected == self.ex.tokens[0].upos
        assert fb.correct == len(tags) - 2

    def test_wrong_length(self) -> None:
        with pytest.raises(errors.InvalidInput):
            check_pos(self.ex, PosAnswer(kind="pos", tags=["NOUN"]))


class TestDependency:
    ex = next(e for e in EXERCISES.values() if isinstance(e, DependencyExercise))

    def gold(self) -> list[DependencyAnswerArc]:
        return [
            DependencyAnswerArc(dependent=t.id, head=t.head, relation=t.deprel)
            for t in self.ex.tokens
        ]

    def test_all_correct(self) -> None:
        fb = check_dependency(self.ex, DependencyAnswer(kind="dependency", arcs=self.gold()))
        assert fb.heads_correct == fb.relations_correct == fb.total

    def test_root_relation_is_implied_by_head_zero(self) -> None:
        arcs = [a.model_copy(update={"relation": None}) if a.head == 0 else a for a in self.gold()]
        fb = check_dependency(self.ex, DependencyAnswer(kind="dependency", arcs=arcs))
        assert fb.relations_correct == fb.total

    def test_subtype_counts_as_partial(self) -> None:
        arcs = self.gold()
        target = next(i for i, a in enumerate(arcs) if a.relation != "root")
        arcs[target] = arcs[target].model_copy(update={"relation": f"{arcs[target].relation}:x"})
        item = check_dependency(self.ex, DependencyAnswer(kind="dependency", arcs=arcs)).items[
            target
        ]
        assert item.relation_status == "partial"
        assert item.head_correct

    def test_wrong_head(self) -> None:
        arcs = self.gold()
        target = next(i for i, a in enumerate(arcs) if a.head != 0)
        arcs[target] = arcs[target].model_copy(update={"head": 0})
        item = check_dependency(self.ex, DependencyAnswer(kind="dependency", arcs=arcs)).items[
            target
        ]
        assert not item.head_correct
        assert item.relation_status == "incorrect"  # "root" given, a real relation expected

    def test_entries_must_cover_every_word(self) -> None:
        with pytest.raises(errors.InvalidInput):
            check_dependency(self.ex, DependencyAnswer(kind="dependency", arcs=self.gold()[:-1]))


class TestConstituency:
    @pytest.mark.parametrize(
        "exercise_id", [k for k, e in EXERCISES.items() if isinstance(e, ConstituencyExercise)]
    )
    def test_every_parse_the_grammar_allows_is_accepted(self, exercise_id: str) -> None:
        ex = EXERCISES[exercise_id]
        assert isinstance(ex, ConstituencyExercise)
        grammar = PRESETS[ex.grammar].grammar
        parses = all_parse_spans(grammar, ex.sentence)
        assert parses
        rng = random.Random(exercise_id)
        for i, spans in enumerate(parses):
            shuffled = list(spans)
            rng.shuffle(shuffled)
            # Submission order only matters for unary chains: restore their outer→inner order.
            shuffled.sort(
                key=lambda s: spans.index(s) if (s[1], s[2]) in _unary_spans(spans) else 0
            )
            fb = check_constituency(ex, grammar, answer(shuffled))
            assert fb.status == "matches", (exercise_id, i, fb.problems)
            assert fb.matched_parse is not None
            assert fb.parse_count == len(parses)
            assert (fb.precision, fb.recall) == (1.0, 1.0)

    def test_ambiguous_sentence_has_two_accepted_readings(self) -> None:
        ex = EXERCISES["grammar-02"]
        assert isinstance(ex, ConstituencyExercise)
        grammar = PRESETS[ex.grammar].grammar
        matched = {
            check_constituency(ex, grammar, answer(spans)).matched_parse
            for spans in all_parse_spans(grammar, ex.sentence)
        }
        assert matched == {1, 2}

    pp = PRESETS["pp-attachment"].grammar
    vp_attach: ClassVar[list[tuple[str, int, int]]] = [
        ("S", 0, 7),
        ("NP", 0, 1),
        ("Pronoun", 0, 1),
        ("VP", 1, 7),
        ("VP", 1, 4),
        ("V", 1, 2),
        ("NP", 2, 4),
        ("Det", 2, 3),
        ("N", 3, 4),
        ("PP", 4, 7),
        ("P", 4, 5),
        ("NP", 5, 7),
        ("Det", 5, 6),
        ("N", 6, 7),
    ]

    def check(self, spans: list[tuple[str, int, int]]) -> object:
        return check_constituency(
            exercise("pp-attachment", "I saw the man with a telescope"), self.pp, answer(spans)
        )

    def test_unlicensed_and_missing_constituents(self) -> None:
        spans = [s for s in self.vp_attach if s not in {("NP", 5, 7), ("Det", 5, 6), ("N", 6, 7)}]
        fb = self.check([*spans, ("NP", 4, 7)])
        statuses = {(c.label, c.start, c.end): c.status for c in fb.constituents}  # type: ignore[attr-defined]
        assert statuses[("NP", 4, 7)] == "unlicensed"
        assert statuses[("NP", 5, 7)] == statuses[("Det", 5, 6)] == "missing"
        assert fb.status == "partial"  # type: ignore[attr-defined]
        # NP(4,7) nests inside PP(4,7) (identical span, added later) and holds P plus two words.
        rules = {p.rule for p in fb.problems if p.code == "no_rule"}  # type: ignore[attr-defined]
        assert rules == {"PP → NP", 'NP → P "a" "telescope"'}

    def test_unary_chain_order_matters(self) -> None:
        # Pronoun above NP is not what the grammar allows (it has NP → Pronoun, not the reverse).
        spans = [s for s in self.vp_attach if s not in {("NP", 0, 1), ("Pronoun", 0, 1)}]
        fb = self.check([("S", 0, 7), ("Pronoun", 0, 1), ("NP", 0, 1), *spans[1:]])
        assert fb.status != "matches"  # type: ignore[attr-defined]
        assert any(p.code == "no_rule" and p.rule == "Pronoun → NP" for p in fb.problems)  # type: ignore[attr-defined]

    def test_crossing_brackets_are_invalid(self) -> None:
        fb = self.check([*self.vp_attach, ("NP", 2, 7)])
        assert fb.status == "invalid"  # type: ignore[attr-defined]
        assert any(p.code == "crossing" for p in fb.problems)  # type: ignore[attr-defined]

    def test_missing_root_and_uncovered_words(self) -> None:
        fb = self.check([("NP", 0, 1), ("Pronoun", 0, 1)])
        codes = [p.code for p in fb.problems]  # type: ignore[attr-defined]
        assert "no_root" in codes
        assert codes.count("uncovered_word") == 6

    def test_unknown_category_and_out_of_range(self) -> None:
        fb = self.check([*self.vp_attach[:-1], ("XP", 6, 7), ("N", 5, 9)])
        codes = {p.code for p in fb.problems}  # type: ignore[attr-defined]
        assert {"unknown_category", "out_of_range"} <= codes

    def test_constituent_valid_only_in_another_reading(self) -> None:
        grammar = 'S -> A | B\nA -> "x"\nB -> "x"'
        fb = check_constituency(
            exercise("g", "x"), grammar, answer([("S", 0, 1), ("A", 0, 1), ("B", 0, 1)])
        )
        statuses = {c.label: c.status for c in fb.constituents}
        assert statuses["B"] == "other_reading"
        assert fb.parse_count == 2

    def test_empty_constituents_need_not_be_drawn(self) -> None:
        grammar = PRESETS["optional-elements"].grammar
        spans = [("S", 0, 2), ("NP", 0, 1), ("N", 0, 1), ("VP", 1, 2), ("V", 1, 2)]
        fb = check_constituency(exercise("optional-elements", "dogs sleep"), grammar, answer(spans))
        assert fb.status == "matches"
        assert fb.problems == []  # NP → N is allowed: the empty Det and AdjP may be left out


def _unary_spans(spans: list[tuple[str, int, int]]) -> set[tuple[int, int]]:
    seen: dict[tuple[int, int], int] = {}
    for _, s, e in spans:
        seen[(s, e)] = seen.get((s, e), 0) + 1
    return {k for k, v in seen.items() if v > 1}
