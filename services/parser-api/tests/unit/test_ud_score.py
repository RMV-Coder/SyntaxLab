"""The gold scorer, on small cases whose scores are worked out by hand."""

from __future__ import annotations

import pytest

from syntaxlab_api.analysis.ud_score import GoldFormatError, Score, read_conllu
from syntaxlab_api.schemas.analysis import (
    DependencyAnalysis,
    DependencyArc,
    SentenceAnalysis,
    Token,
)

# "Maganda ang bata ." with gold relations; four plain words.
PLAIN = """# sent_id = a
# text = Maganda ang bata.
1\tMaganda\tganda\tADJ\t_\t_\t0\troot\t_\t_
2\tang\tang\tDET\t_\tCase=Nom\t3\tdet\t_\t_
3\tbata\tbata\tNOUN\t_\t_\t1\tnsubj\t_\tSpaceAfter=No
4\t.\t.\tPUNCT\t_\t_\t1\tpunct\t_\t_
"""

# "magandang bata": the first token is a multiword token (maganda + -ng).
LINKER = """# text = magandang bata
1-2\tmagandang\t_\t_\t_\t_\t_\t_\t_\t_
1\tmaganda\tganda\tADJ\t_\t_\t3\tamod\t_\t_
2\tng\tna\tPART\t_\t_\t1\tmark\t_\t_
3\tbata\tbata\tNOUN\t_\t_\t0\troot\t_\t_
"""


def analysis(*words: tuple[str, int, int, str, str, int, str]) -> SentenceAnalysis:
    """Words as (form, start, end, upos, lemma, head, relation), numbered from 1."""
    return SentenceAnalysis(
        text=" ".join(w[0] for w in words),
        tokens=[
            Token(id=i, form=w[0], start_char=w[1], end_char=w[2], upos=w[3], lemma=w[4])
            for i, w in enumerate(words, start=1)
        ],
        dependency=DependencyAnalysis(
            scheme="ud-2",
            arcs=[
                DependencyArc(dependent=i, head=w[5], relation=w[6])
                for i, w in enumerate(words, start=1)
            ],
        ),
    )


def perfect() -> SentenceAnalysis:
    sentence = analysis(
        ("Maganda", 0, 7, "ADJ", "ganda", 0, "root"),
        ("ang", 8, 11, "DET", "ang", 3, "det"),
        ("bata", 12, 16, "NOUN", "bata", 1, "nsubj"),
        (".", 16, 17, "PUNCT", ".", 1, "punct"),
    )
    tokens = list(sentence.tokens)
    tokens[1] = tokens[1].model_copy(update={"feats": {"Case": "Nom"}})
    return sentence.model_copy(update={"tokens": tokens})


class TestReadConllu:
    def test_locates_tokens_and_reads_columns(self) -> None:
        [sentence] = read_conllu(PLAIN)
        assert sentence.meta["sent_id"] == "a"
        assert sentence.text == "Maganda ang bata."
        assert sentence.token_spans == [(0, 7), (8, 11), (12, 16), (16, 17)]
        assert sentence.words[1].feats == {"Case": "Nom"}
        assert sentence.words[0].head == 0

    def test_multiword_token_counts_once_and_its_words_have_no_span(self) -> None:
        [sentence] = read_conllu(LINKER)
        assert sentence.token_spans == [(0, 9), (10, 14)]
        assert [w.span for w in sentence.words] == [None, None, (10, 14)]

    def test_skips_empty_nodes(self) -> None:
        extra = PLAIN.rstrip("\n") + "\n4.1\tx\tx\tX\t_\t_\t_\t_\t_\t_\n"
        assert len(read_conllu(extra)[0].words) == 4

    def test_reads_several_sentences(self) -> None:
        assert len(read_conllu(PLAIN + "\n" + LINKER)) == 2

    @pytest.mark.parametrize(
        "content",
        [
            "1\tx\tx\tX\t_\t_\t0\troot\t_\t_\n",  # no # text
            "# text = a\n1\tb\tb\tX\t_\t_\t0\troot\t_\t_\n",  # form not in the text
            "# text = a\n1\ta\ta\n",  # too few columns
        ],
    )
    def test_rejects_malformed_gold(self, content: str) -> None:
        with pytest.raises(GoldFormatError):
            read_conllu(content)


class TestScore:
    def test_perfect_analysis_scores_100_everywhere(self) -> None:
        score = Score()
        score.add(read_conllu(PLAIN)[0], [perfect()])
        for metric in ("Tokens", "Words", "UPOS", "UFeats", "Lemmas", "UAS", "LAS", "LAS_full"):
            assert score.f1(metric) == pytest.approx(100.0), metric
        assert score.f1("LAS_no_punct") == pytest.approx(100.0)
        assert score.exact_tokenization == 1
        assert score.split_sentences == 0

    def test_wrong_label_costs_las_but_not_uas(self) -> None:
        system = perfect()
        arcs = list(system.dependency.arcs)  # type: ignore[union-attr]
        arcs[2] = arcs[2].model_copy(update={"relation": "obj"})
        system = system.model_copy(
            update={"dependency": DependencyAnalysis(scheme="ud-2", arcs=arcs)}
        )
        score = Score()
        score.add(read_conllu(PLAIN)[0], [system])
        assert score.f1("UAS") == pytest.approx(100.0)
        assert score.f1("LAS") == pytest.approx(75.0)  # 3 of 4

    def test_subtype_counts_for_las_but_not_las_full(self) -> None:
        system = perfect()
        arcs = list(system.dependency.arcs)  # type: ignore[union-attr]
        arcs[2] = arcs[2].model_copy(update={"relation": "nsubj:pass"})
        system = system.model_copy(
            update={"dependency": DependencyAnalysis(scheme="ud-2", arcs=arcs)}
        )
        score = Score()
        score.add(read_conllu(PLAIN)[0], [system])
        assert score.f1("LAS") == pytest.approx(100.0)
        assert score.f1("LAS_full") == pytest.approx(75.0)

    def test_wrong_head_costs_both(self) -> None:
        system = perfect()
        arcs = list(system.dependency.arcs)  # type: ignore[union-attr]
        arcs[3] = arcs[3].model_copy(update={"head": 3})  # punct on "bata", gold on "Maganda"
        system = system.model_copy(
            update={"dependency": DependencyAnalysis(scheme="ud-2", arcs=arcs)}
        )
        score = Score()
        score.add(read_conllu(PLAIN)[0], [system])
        assert score.f1("UAS") == pytest.approx(75.0)
        assert score.f1("LAS") == pytest.approx(75.0)
        assert score.f1("LAS_no_punct") == pytest.approx(100.0)  # only punctuation was wrong

    def test_unsplit_multiword_token_counts_against_recall_only(self) -> None:
        system = analysis(
            ("magandang", 0, 9, "ADJ", "ganda", 2, "amod"),
            ("bata", 10, 14, "NOUN", "bata", 0, "root"),
        )
        score = Score()
        score.add(read_conllu(LINKER)[0], [system])
        # Surface tokens match exactly.
        assert score.f1("Tokens") == pytest.approx(100.0)
        assert score.exact_tokenization == 1
        # Syntactic words: 1 aligned of 2 system (P 50) and 3 gold (R 33.3).
        assert score.f1("Words") == pytest.approx(40.0)
        # "bata" is the root in both.
        assert score.f1("LAS") == pytest.approx(40.0)

    def test_split_hyphen_word_misses_the_word_and_its_dependents(self) -> None:
        gold = read_conllu(
            "# text = nag-aral siya\n"
            "1\tnag-aral\taral\tVERB\t_\t_\t0\troot\t_\t_\n"
            "2\tsiya\tsiya\tPRON\t_\t_\t1\tnsubj\t_\t_\n"
        )[0]
        system = analysis(
            ("nag", 0, 3, "VERB", "nag", 0, "root"),
            ("-", 3, 4, "PUNCT", "-", 1, "punct"),
            ("aral", 4, 8, "VERB", "aral", 1, "conj"),
            ("siya", 9, 13, "PRON", "siya", 1, "nsubj"),
        )
        score = Score()
        score.add(gold, [system])
        assert score.correct["Words"] == 1
        assert score.correct["UAS"] == 0  # its head is not aligned with the gold head
        assert score.exact_tokenization == 0

    def test_a_split_gold_sentence_is_counted_and_its_second_root_is_wrong(self) -> None:
        first = analysis(("Maganda", 0, 7, "ADJ", "ganda", 0, "root"))
        second = analysis(
            ("ang", 8, 11, "DET", "ang", 2, "det"),
            ("bata", 12, 16, "NOUN", "bata", 0, "root"),
            (".", 16, 17, "PUNCT", ".", 2, "punct"),
        )
        score = Score()
        score.add(read_conllu(PLAIN)[0], [first, second])
        assert score.split_sentences == 1
        assert score.correct["UAS"] == 2  # Maganda and ang; bata's and .'s heads are wrong

    def test_relation_scores_use_the_full_label(self) -> None:
        score = Score()
        score.add(read_conllu(PLAIN)[0], [perfect()])
        assert score.relation_scores("nsubj") == pytest.approx((100.0, 100.0))
        assert score.relation_scores("obj:agent") == pytest.approx((0.0, 0.0))

    def test_empty_score_is_zero_not_a_division_error(self) -> None:
        assert Score().f1("LAS") == 0.0

    def test_needs_character_offsets(self) -> None:
        system = perfect()
        tokens = [t.model_copy(update={"start_char": None}) for t in system.tokens]
        with pytest.raises(ValueError, match="offsets"):
            Score().add(read_conllu(PLAIN)[0], [system.model_copy(update={"tokens": tokens})])
