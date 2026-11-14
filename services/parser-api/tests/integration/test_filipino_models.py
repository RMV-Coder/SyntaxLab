"""Linguistic regression tests against the real Tagalog model and gold UD annotations.

Run with:  uv run syntaxlab-api download-models --language tl && uv run pytest -m models -s

Every reference analysis is a treebank's manual annotation. Thresholds sit below the measured
scores (docs/research/nlp-model-evaluation.md, section 3.8), so they catch regressions (model
upgrades, tokenizer or normalization bugs) without failing on ordinary variation.

The glossary tests read the model's own label inventory, so a label the model can produce never
reaches a student without an explanation.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from syntaxlab_api.analysis.ud_score import Score, read_conllu
from syntaxlab_api.analysis.validate import validate_sentence
from syntaxlab_api.engines.base import Engine
from syntaxlab_api.glossary import Glossary, load_glossaries
from syntaxlab_api.languages.config import load_languages_file
from syntaxlab_api.languages.registry import LanguageRegistry
from syntaxlab_api.schemas.analysis import Capability, SentenceAnalysis, StructureKind
from syntaxlab_api.settings import Settings

pytestmark = pytest.mark.models

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ud"
DEPENDENCY = frozenset({StructureKind.DEPENDENCY})

# Measured on the bundled fixtures: see the printed table and section 3.8 of the evaluation.
MIN_SCORES = {
    "tl_trg_regression.conllu": {"Tokens": 98.0, "UPOS": 74.0, "UAS": 90.0, "LAS": 73.0},
    "tl_newscrawl_regression.conllu": {"Tokens": 94.0, "UPOS": 80.0, "UAS": 66.0, "LAS": 62.0},
}


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    settings = Settings(enabled_languages=["tl"], preload=False)
    registry = LanguageRegistry.from_config(load_languages_file(settings.languages_file), settings)
    loaded = next(iter(registry)).engine
    loaded.load()
    yield loaded
    loaded.close()


@pytest.fixture(scope="module")
def glossaries() -> dict[str, Glossary]:
    settings = Settings()
    config = load_languages_file(settings.languages_file)
    return load_glossaries(settings.glossary_dir, config.schemes)


def analyze_one(engine: Engine, text: str) -> SentenceAnalysis:
    [sentence] = engine.analyze(text, DEPENDENCY)
    validate_sentence(sentence)
    return sentence


@pytest.mark.parametrize("fixture", sorted(MIN_SCORES))
def test_scores_on_gold_treebanks(engine: Engine, fixture: str) -> None:
    gold = read_conllu((FIXTURES / fixture).read_text(encoding="utf-8"))
    score = Score()
    for sentence in gold:
        analyses = engine.analyze(sentence.text, DEPENDENCY)
        for analysis in analyses:
            validate_sentence(analysis)
        score.add(sentence, analyses)
    measured = {metric: round(score.f1(metric), 1) for metric in MIN_SCORES[fixture]}
    print(f"\n{fixture}: {len(gold)} sentences, {measured}")
    for metric, minimum in MIN_SCORES[fixture].items():
        assert score.f1(metric) >= minimum, f"{metric} fell to {score.f1(metric):.1f}"


class TestTokenization:
    def test_hyphenated_words_stay_whole(self, engine: Engine) -> None:
        # From the treebank's conventions; the default spaCy tokenizer splits this into three.
        sentence = analyze_one(engine, "Nag-aral siya sa paaralan.")
        assert sentence.tokens[0].form == "Nag-aral"

    def test_extra_whitespace_changes_nothing_but_the_offsets(self, engine: Engine) -> None:
        plain = analyze_one(engine, "Binabasa ng titser ang diyaryo.")
        spaced = analyze_one(engine, "Binabasa  ng\ntitser   ang diyaryo.")
        assert [t.form for t in spaced.tokens] == [t.form for t in plain.tokens]
        assert spaced.dependency == plain.dependency
        for token in spaced.tokens:
            assert "Binabasa  ng\ntitser   ang diyaryo."[token.start_char : token.end_char] == (
                token.form
            )


class TestSentences:
    def test_two_sentences_are_not_parsed_as_one_tree(self, engine: Engine) -> None:
        assert len(engine.analyze("Gumising ang bata. Natulog ang nanay.", DEPENDENCY)) == 2

    @pytest.mark.parametrize(
        "text",
        [
            "Dumating si Dr. Santos kahapon.",
            "Sinabi ni Sen. Roxas ito.",
            "Dumating si Jose P. Rizal kahapon.",
        ],
    )
    def test_abbreviations_end_no_sentence(self, engine: Engine, text: str) -> None:
        analyze_one(engine, text)  # exactly one sentence, or it fails

    def test_a_sentence_ending_in_an_abbreviation_can_still_be_followed_by_a_question(
        self, engine: Engine
    ) -> None:
        assert len(engine.analyze("Sino ang dumating? Si Dr. Santos.", DEPENDENCY)) == 2


class TestFaithfulOutput:
    def test_no_xpos_is_reported(self, engine: Engine) -> None:
        # The pipeline's tagger only repeats POS and features; it is not a treebank tag set.
        assert all(t.xpos is None for t in analyze_one(engine, "Gumising ang bata.").tokens)

    def test_root_uses_the_ud_label(self, engine: Engine) -> None:
        sentence = analyze_one(engine, "Gumising ang bata.")
        assert sentence.dependency is not None
        roots = [a for a in sentence.dependency.arcs if a.head == 0]
        assert [a.relation for a in roots] == ["root"]

    def test_never_offers_constituency(self, engine: Engine) -> None:
        assert Capability.CONSTITUENCY not in engine.capabilities()


class TestGlossaryCoverage:
    def nlp(self, engine: Engine) -> Any:
        return engine._nlp  # type: ignore[attr-defined]

    def test_every_relation_has_a_definition(
        self, engine: Engine, glossaries: dict[str, Glossary]
    ) -> None:
        labels = self.nlp(engine).get_pipe("parser").labels
        known = glossaries["ud-2"].entries
        missing = [x for x in labels if x != "ROOT" and x not in known]
        assert not missing

    def test_every_tag_and_feature_value_has_a_definition(
        self, engine: Engine, glossaries: dict[str, Glossary]
    ) -> None:
        pos, features = set(), set()
        for label in self.nlp(engine).get_pipe("morphologizer").labels:
            for item in label.split("|"):
                key, _, value = item.partition("=")
                if key == "POS":
                    pos.add(value)
                elif value:
                    features |= {(key, v) for v in value.split(",")}
        assert not [p for p in pos if p not in glossaries["ud-upos"].entries]
        entries = glossaries["ud-feats"].entries
        missing = [
            (key, value)
            for key, value in features
            if key not in entries or value not in entries[key].values
        ]
        assert not missing

    def test_samples_parse_and_validate(self, engine: Engine) -> None:
        settings = Settings()
        config = load_languages_file(settings.languages_file)
        tl = next(lang for lang in config.languages if lang.code == "tl")
        assert tl.samples
        for sample in tl.samples:
            analyze_one(engine, sample.text)
