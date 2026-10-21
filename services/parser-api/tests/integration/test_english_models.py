"""Linguistic regression tests against real English models and gold UD annotations.

Run with:  uv run syntaxlab-api download-models --language en && uv run pytest -m models -s

Thresholds sit below the measured scores (UD EWT test LAS 89.7, see
docs/research/nlp-model-evaluation.md) so that they catch regressions (model upgrades,
normalization bugs) without failing on ordinary variation.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from syntaxlab_api.analysis.validate import validate_sentence
from syntaxlab_api.engines.base import Engine
from syntaxlab_api.languages.config import load_languages_file
from syntaxlab_api.languages.registry import LanguageRegistry
from syntaxlab_api.schemas.analysis import SentenceAnalysis, StructureKind
from syntaxlab_api.settings import Settings

pytestmark = pytest.mark.models

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ud" / "en_ewt_regression.conllu"
BOTH = frozenset({StructureKind.DEPENDENCY, StructureKind.CONSTITUENCY})

MIN_TOKENIZATION_MATCH = 0.85
MIN_LAS_OVERALL = 0.85
MIN_LAS_PER_CATEGORY = 0.75


@dataclass
class GoldSentence:
    sent_id: str
    text: str
    categories: list[str]
    forms: list[str]
    heads: list[int]
    relations: list[str]
    upos: list[str]


@dataclass
class Score:
    sentences: int = 0
    words: int = 0
    uas: int = 0
    las: int = 0
    upos: int = 0
    tokenization_mismatches: list[str] = field(default_factory=list)


def read_gold() -> list[GoldSentence]:
    out = []
    for block in FIXTURE.read_text(encoding="utf-8").strip().split("\n\n"):
        lines = block.splitlines()
        meta = {
            k.strip(): v.strip()
            for k, _, v in (line[2:].partition("=") for line in lines if line.startswith("# "))
        }
        if "text" not in meta:
            continue
        rows = [line.split("\t") for line in lines if line and line[0].isdigit()]
        words = [r for r in rows if r[0].isdigit()]
        out.append(
            GoldSentence(
                sent_id=meta["sent_id"],
                text=meta["text"],
                categories=meta["syntaxlab_categories"].split(","),
                forms=[r[1] for r in words],
                heads=[int(r[6]) for r in words],
                relations=[r[7] for r in words],
                upos=[r[3] for r in words],
            )
        )
    return out


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    settings = Settings(enabled_languages=["en"], cpu_threads=2)
    registry = LanguageRegistry.from_config(load_languages_file(settings.languages_file), settings)
    eng = registry.get("en").engine
    eng.load()  # fails loudly if models were not downloaded
    yield eng
    eng.close()


def analyze_one(engine: Engine, text: str) -> SentenceAnalysis:
    sentences = engine.analyze(text, BOTH)
    for s in sentences:
        validate_sentence(s)
    assert len(sentences) >= 1
    return sentences[0]


class TestKnownAnalyses:
    """Minimal, uncontroversial UD/PTB facts about textbook sentences."""

    def test_simple_transitive_clause(self, engine: Engine) -> None:
        s = analyze_one(engine, "The child is eating rice.")
        forms = {t.id: t.form for t in s.tokens}
        assert s.dependency is not None
        arcs = {
            (forms[a.dependent], forms.get(a.head, "ROOT"), a.relation) for a in s.dependency.arcs
        }
        assert {
            ("eating", "ROOT", "root"),
            ("child", "eating", "nsubj"),
            ("is", "eating", "aux"),
            ("rice", "eating", "obj"),
            ("The", "child", "det"),
        } <= arcs
        assert s.constituency is not None
        nodes = {n.id: n for n in s.constituency.nodes}
        root = nodes[s.constituency.root]
        clause = nodes[root.children[0]]
        assert clause.label == "S"
        assert [nodes[c].label for c in clause.children][:2] == ["NP", "VP"]

    def test_contraction_kept_as_multiword_token(self, engine: Engine) -> None:
        s = analyze_one(engine, "I don't know.")
        assert [(m.form, m.first, m.last) for m in s.multiword_tokens] == [("don't", 2, 3)]
        assert [t.form for t in s.tokens][:3] == ["I", "do", "n't"]

    def test_passive(self, engine: Engine) -> None:
        # UD English (EWT >= 2.x) marks the by-phrase agent of a passive as obl:agent.
        s = analyze_one(engine, "The letter was written by Mary.")
        forms = {t.id: t.form for t in s.tokens}
        assert s.dependency is not None
        arcs = {
            (forms[a.dependent], forms.get(a.head, "ROOT"), a.relation) for a in s.dependency.arcs
        }
        assert {
            ("letter", "written", "nsubj:pass"),
            ("was", "written", "aux:pass"),
            ("Mary", "written", "obl:agent"),
            ("by", "Mary", "case"),
        } <= arcs

    def test_character_offsets_point_into_text(self, engine: Engine) -> None:
        text = "Students read “difficult” books (sometimes)."
        s = analyze_one(engine, text)
        for t in s.tokens:
            if t.start_char is not None and t.end_char is not None:
                assert text[t.start_char : t.end_char] == t.form


def test_gold_regression(engine: Engine) -> None:
    gold = read_gold()
    assert len(gold) >= 60
    scores: dict[str, Score] = defaultdict(Score)
    for g in gold:
        predicted = analyze_one(engine, g.text)
        forms = [t.form for t in predicted.tokens]
        buckets = [scores["ALL"], *(scores[c] for c in g.categories)]
        if forms != g.forms:
            for b in buckets:
                b.tokenization_mismatches.append(g.sent_id)
            continue
        assert predicted.dependency is not None
        arcs = {a.dependent: a for a in predicted.dependency.arcs}
        for i, token in enumerate(predicted.tokens):
            arc = arcs[token.id]
            head_ok = arc.head == g.heads[i]
            for b in buckets:
                b.words += 1
                b.uas += head_ok
                b.las += head_ok and arc.relation == g.relations[i]
                b.upos += token.upos == g.upos[i]
        for b in buckets:
            b.sentences += 1

    lines = [
        f"{'category':22s} {'sents':>5s} {'tok-mismatch':>12s} {'UPOS':>6s} {'UAS':>6s} {'LAS':>6s}"
    ]
    for name, sc in sorted(scores.items()):
        w = max(sc.words, 1)
        lines.append(
            f"{name:22s} {sc.sentences:5d} {len(sc.tokenization_mismatches):12d} "
            f"{sc.upos / w:6.3f} {sc.uas / w:6.3f} {sc.las / w:6.3f}"
        )
    print("\n" + "\n".join(lines))

    overall = scores["ALL"]
    total = overall.sentences + len(overall.tokenization_mismatches)
    assert overall.sentences / total >= MIN_TOKENIZATION_MATCH, overall.tokenization_mismatches
    assert overall.las / overall.words >= MIN_LAS_OVERALL
    for name, sc in scores.items():
        if sc.words:
            assert sc.las / sc.words >= MIN_LAS_PER_CATEGORY, f"{name}: LAS {sc.las / sc.words:.3f}"
