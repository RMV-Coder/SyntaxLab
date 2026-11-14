"""Score analyses of raw text against gold CoNLL-U, for evaluation scripts and regression tests.

The method follows the CoNLL 2018 shared task, simplified for one case: each gold sentence is
analyzed on its own, so words are aligned within a sentence.

- A system word aligns with a gold word when both cover exactly the same characters.
- Gold syntactic words inside a multiword token (Tagalog *magandang* = *maganda* + *-ng*) have no
  characters of their own. They align only if the system produced the same split, which is why
  they count against recall for a tokenizer that does not split them.
- Every metric is an F1: correct / system words, against correct / gold words.
- A head is correct when the system's head is aligned with the gold head, or both are the root.
- ``LAS`` compares the universal part of a relation (``obj:agent`` counts as ``obj``), as the
  shared task does. ``LAS_full`` compares the whole label, and ``LAS_no_punct`` leaves out
  punctuation, as ``spacy evaluate`` does.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from syntaxlab_api.schemas.analysis import SentenceAnalysis

METRICS = (
    "Tokens",
    "Words",
    "UPOS",
    "UFeats",
    "Lemmas",
    "UAS",
    "LAS",
    "LAS_full",
    "LAS_no_punct",
)
_PUNCT = "PUNCT"


class GoldFormatError(ValueError):
    """The gold file cannot be read, or its words do not match its sentence text."""


@dataclass(frozen=True)
class GoldWord:
    id: int
    form: str
    lemma: str
    upos: str
    feats: dict[str, str]
    head: int
    relation: str
    #: Character span in the sentence text; None for a word inside a multiword token.
    span: tuple[int, int] | None


@dataclass(frozen=True)
class GoldSentence:
    text: str
    words: list[GoldWord]
    #: Character spans of the surface tokens (a multiword token counts once).
    token_spans: list[tuple[int, int]]
    #: The file's own comment lines, e.g. {"sent_id": "...", "text": "..."}.
    meta: dict[str, str] = field(default_factory=dict)


def _parse_feats(raw: str) -> dict[str, str]:
    if raw == "_":
        return {}
    return dict(item.split("=", 1) for item in raw.split("|"))


def read_conllu(content: str) -> list[GoldSentence]:
    """Parse CoNLL-U, locating every surface token in the sentence's ``# text``."""
    return [_read_sentence(block) for block in content.strip().split("\n\n")]


def _read_sentence(block: str) -> GoldSentence:
    lines = block.splitlines()
    meta = {
        key.strip(): value.strip()
        for key, _, value in (line[2:].partition("=") for line in lines if line[:2] == "# ")
    }
    text = next((line[9:] for line in lines if line.startswith("# text = ")), None)
    if text is None:
        raise GoldFormatError(f"sentence without '# text': {block[:80]!r}")
    words: list[GoldWord] = []
    token_spans: list[tuple[int, int]] = []
    position = 0
    inside_until = 0  # last word id covered by the multiword token being read
    for line in lines:
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) != 10:
            raise GoldFormatError(f"expected 10 columns: {line!r}")
        word_id = columns[0]
        if "." in word_id:  # empty node of an enhanced graph
            continue
        span: tuple[int, int] | None = None
        if "-" in word_id or int(word_id) > inside_until:
            start = text.find(columns[1], position)
            if start < 0:
                raise GoldFormatError(f"token {columns[1]!r} not found in {text!r}")
            position = start + len(columns[1])
            span = (start, position)
            token_spans.append(span)
        if "-" in word_id:
            inside_until = int(word_id.split("-")[1])
            continue
        words.append(
            GoldWord(
                id=int(word_id),
                form=columns[1],
                lemma=columns[2],
                upos=columns[3],
                feats=_parse_feats(columns[5]),
                head=int(columns[6]),
                relation=columns[7],
                span=span,
            )
        )
    return GoldSentence(text=text, words=words, token_spans=token_spans, meta=meta)


@dataclass
class Score:
    """Running totals over sentences."""

    system_words: int = 0
    gold_words: int = 0
    system_tokens: int = 0
    gold_tokens: int = 0
    system_no_punct: int = 0
    gold_no_punct: int = 0
    correct: Counter[str] = field(default_factory=Counter)
    relation_system: Counter[str] = field(default_factory=Counter)
    relation_gold: Counter[str] = field(default_factory=Counter)
    relation_correct: Counter[str] = field(default_factory=Counter)
    sentences: int = 0
    exact_tokenization: int = 0
    #: Gold sentences the system split into more than one.
    split_sentences: int = 0

    def add(self, gold: GoldSentence, system: list[SentenceAnalysis]) -> None:
        self.sentences += 1
        self.split_sentences += len(system) > 1
        self.gold_words += len(gold.words)
        self.gold_tokens += len(gold.token_spans)
        self.gold_no_punct += sum(w.upos != _PUNCT for w in gold.words)
        for word in gold.words:
            self.relation_gold[word.relation] += 1

        gold_by_span = {w.span: w for w in gold.words if w.span is not None}
        system_spans: list[tuple[int, int]] = []
        for analysis in system:
            arcs = (
                {a.dependent: a for a in analysis.dependency.arcs}
                if analysis.dependency is not None
                else {}
            )
            spans = {t.id: _span(t.start_char, t.end_char) for t in analysis.tokens}
            system_spans.extend(spans.values())
            for token in analysis.tokens:
                self.system_words += 1
                self.system_tokens += 1
                self.system_no_punct += token.upos != _PUNCT
                arc = arcs.get(token.id)
                if arc is not None:
                    self.relation_system[arc.relation] += 1
                aligned = gold_by_span.get(spans[token.id])
                if aligned is None:
                    continue
                self.correct["Words"] += 1
                self.correct["UPOS"] += token.upos == aligned.upos
                self.correct["UFeats"] += token.feats == aligned.feats
                self.correct["Lemmas"] += token.lemma == aligned.lemma
                if arc is None:
                    continue
                head_correct = (
                    arc.head == 0
                    if aligned.head == 0
                    else (arc.head != 0 and spans[arc.head] == _gold_span(gold, aligned.head))
                )
                self.correct["UAS"] += head_correct
                if not head_correct:
                    continue
                if arc.relation.split(":")[0] == aligned.relation.split(":")[0]:
                    self.correct["LAS"] += 1
                    self.correct["LAS_no_punct"] += aligned.upos != _PUNCT
                if arc.relation == aligned.relation:
                    self.correct["LAS_full"] += 1
                    self.relation_correct[aligned.relation] += 1

        gold_tokens = set(gold.token_spans)
        self.correct["Tokens"] += sum(span in gold_tokens for span in system_spans)
        self.exact_tokenization += sorted(system_spans) == sorted(gold.token_spans)

    def f1(self, metric: str) -> float:
        """F1 of ``metric`` as a percentage (0 when nothing was scored)."""
        system, gold = self._denominators(metric)
        correct = self.correct[metric]
        if not correct:
            return 0.0
        precision, recall = correct / system, correct / gold
        return 100 * 2 * precision * recall / (precision + recall)

    def _denominators(self, metric: str) -> tuple[int, int]:
        if metric == "Tokens":
            return self.system_tokens, self.gold_tokens
        if metric == "LAS_no_punct":
            return self.system_no_punct, self.gold_no_punct
        return self.system_words, self.gold_words

    def relation_scores(self, relation: str) -> tuple[float, float]:
        """Full-label (precision, recall) of one relation, as percentages."""
        correct = self.relation_correct[relation]
        return (
            100 * correct / max(self.relation_system[relation], 1),
            100 * correct / max(self.relation_gold[relation], 1),
        )


def _span(start: int | None, end: int | None) -> tuple[int, int]:
    if start is None or end is None:
        raise ValueError("scoring needs character offsets on every token")
    return start, end


def _gold_span(gold: GoldSentence, word_id: int) -> tuple[int, int] | None:
    return next((w.span for w in gold.words if w.id == word_id), None)
