from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from syntaxlab_api.glossary import Glossary, load_glossaries
from syntaxlab_api.languages.config import ConfigError, SchemeConfig, load_languages_file
from syntaxlab_api.settings import SERVICE_ROOT

GLOSSARY_DIR = SERVICE_ROOT / "data" / "glossary"
FIXTURE = SERVICE_ROOT / "tests" / "fixtures" / "ud" / "en_ewt_regression.conllu"

UD_UNIVERSAL_RELATIONS = {
    "acl",
    "advcl",
    "advmod",
    "amod",
    "appos",
    "aux",
    "case",
    "cc",
    "ccomp",
    "clf",
    "compound",
    "conj",
    "cop",
    "csubj",
    "dep",
    "det",
    "discourse",
    "dislocated",
    "expl",
    "fixed",
    "flat",
    "goeswith",
    "iobj",
    "list",
    "mark",
    "nmod",
    "nsubj",
    "nummod",
    "obj",
    "obl",
    "orphan",
    "parataxis",
    "punct",
    "reparandum",
    "root",
    "vocative",
    "xcomp",
}
UPOS = {
    "ADJ",
    "ADP",
    "ADV",
    "AUX",
    "CCONJ",
    "DET",
    "INTJ",
    "NOUN",
    "NUM",
    "PART",
    "PRON",
    "PROPN",
    "PUNCT",
    "SCONJ",
    "SYM",
    "VERB",
    "X",
}
# Leipzig Glossing Rules, Appendix: list of standard abbreviations (plus person numbers).
LGR = {
    "1",
    "2",
    "3",
    "A",
    "ABL",
    "ABS",
    "ACC",
    "ADJ",
    "ADV",
    "AGR",
    "ALL",
    "ANTIP",
    "APPL",
    "ART",
    "AUX",
    "BEN",
    "CAUS",
    "CLF",
    "COM",
    "COMP",
    "COMPL",
    "COND",
    "COP",
    "CVB",
    "DAT",
    "DECL",
    "DEF",
    "DEM",
    "DET",
    "DIST",
    "DISTR",
    "DU",
    "DUR",
    "ERG",
    "EXCL",
    "F",
    "FOC",
    "FUT",
    "GEN",
    "IMP",
    "INCL",
    "IND",
    "INDF",
    "INF",
    "INS",
    "INTR",
    "IPFV",
    "IRR",
    "LOC",
    "M",
    "N",
    "NEG",
    "NMLZ",
    "NOM",
    "OBJ",
    "OBL",
    "P",
    "PASS",
    "PFV",
    "PL",
    "POSS",
    "PRED",
    "PRF",
    "PRS",
    "PROG",
    "PROH",
    "PROX",
    "PST",
    "PTCP",
    "PURP",
    "Q",
    "QUOT",
    "RECP",
    "REFL",
    "REL",
    "RES",
    "S",
    "SBJ",
    "SBJV",
    "SG",
    "TOP",
    "TR",
    "VOC",
}
PTB_LABELS_IN_PRACTICE = {
    "ROOT",
    "S",
    "SBAR",
    "SBARQ",
    "SINV",
    "SQ",
    "NP",
    "NML",
    "VP",
    "PP",
    "ADJP",
    "ADVP",
    "QP",
    "PRT",
    "WHNP",
    "WHADVP",
    "FRAG",
    "PRN",
    "UCP",
    "CC",
    "CD",
    "DT",
    "IN",
    "JJ",
    "MD",
    "NN",
    "NNS",
    "NNP",
    "PRP",
    "PRP$",
    "RB",
    "TO",
    "VB",
    "VBD",
    "VBG",
    "VBN",
    "VBP",
    "VBZ",
    "WDT",
    "WP",
    "WRB",
    ".",
    ",",
    "``",
    "''",
    "-LRB-",
    "-RRB-",
    "HYPH",
    "POS",
    "RP",
    "EX",
    "UH",
}


@pytest.fixture(scope="module")
def shipped() -> dict[str, Glossary]:
    config = load_languages_file(SERVICE_ROOT / "config" / "languages.yaml")
    return load_glossaries(GLOSSARY_DIR, config.schemes)


def test_every_declared_scheme_has_a_glossary(shipped: dict[str, Glossary]) -> None:
    config = load_languages_file(SERVICE_ROOT / "config" / "languages.yaml")
    assert set(shipped) == set(config.schemes)


def test_ud_relations_cover_universal_set_and_gold_data(shipped: dict[str, Glossary]) -> None:
    entries = shipped["ud-2"].entries
    assert set(entries) >= UD_UNIVERSAL_RELATIONS
    gold = {
        line.split("\t")[7]
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line and line[0].isdigit() and line.split("\t")[0].isdigit()
    }
    assert gold <= set(entries), sorted(gold - set(entries))


def test_upos_complete_with_families(shipped: dict[str, Glossary]) -> None:
    entries = shipped["ud-upos"].entries
    assert set(entries) == UPOS
    assert all(e.family is not None for e in entries.values())


def test_feature_glosses_marked_standard_are_leipzig(shipped: dict[str, Glossary]) -> None:
    for feature, entry in shipped["ud-feats"].entries.items():
        for value, v in entry.values.items():
            if v.gloss and v.gloss_standard:
                assert v.gloss in LGR, f"{feature}={value}: {v.gloss} is not a Leipzig abbreviation"


def test_ptb_labels_covered(shipped: dict[str, Glossary]) -> None:
    assert set(shipped["ptb-revised"].entries) >= PTB_LABELS_IN_PRACTICE


def test_every_entry_has_text(shipped: dict[str, Glossary]) -> None:
    for glossary in shipped.values():
        for label, entry in glossary.entries.items():
            assert entry.name.strip(), (glossary.id, label)
            assert entry.definition.strip(), (glossary.id, label)


class TestLoading:
    schemes: ClassVar[dict[str, SchemeConfig]] = {"demo": SchemeConfig(name="Demo scheme")}

    def test_missing_file_is_allowed(self, tmp_path: Path) -> None:
        assert load_glossaries(tmp_path, self.schemes) == {}

    def test_malformed_file_fails(self, tmp_path: Path) -> None:
        (tmp_path / "demo.yaml").write_text("id: demo\nkind: x\nentries: {A: {name: a}}\n")
        with pytest.raises(ConfigError, match="invalid glossary"):
            load_glossaries(tmp_path, self.schemes)

    def test_id_mismatch_fails(self, tmp_path: Path) -> None:
        (tmp_path / "demo.yaml").write_text("id: other\nkind: x\nentries: {}\n")
        with pytest.raises(ConfigError, match="expected 'demo'"):
            load_glossaries(tmp_path, self.schemes)

    def test_unsafe_scheme_id_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="invalid scheme id"):
            load_glossaries(tmp_path, {"../etc": SchemeConfig(name="x")})

    def test_scheme_metadata_merged(self, tmp_path: Path) -> None:
        (tmp_path / "demo.yaml").write_text(
            "id: demo\nkind: pos\nentries:\n  A: {name: a, definition: def, family: nominal}\n"
        )
        g = load_glossaries(tmp_path, self.schemes)["demo"]
        assert (g.name, g.kind, g.entries["A"].family) == ("Demo scheme", "pos", "nominal")
