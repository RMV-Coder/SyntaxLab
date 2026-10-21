"""Build part-of-speech and dependency exercises from UD English-EWT (gold annotations).

Sentences are *selected*, never written: every answer key is the treebank's manual annotation.
Selection rules (deterministic, so the bank is reproducible):

- 5-10 syntactic words, no multiword tokens, no typos (Typo=Yes) or abbreviations, no
  relations that need special explanation for beginners (dep, goeswith, reparandum, orphan,
  list, dislocated, vocative);
- complete clauses: the root has an overt subject;
- simple sentence punctuation only;
- the POS and dependency sets use different sentences.

    uv run python scripts/build_learning_exercises.py

Source: UD_English-EWT, tag r2.18, dev split. License: CC BY-SA 4.0 (data/exercises/README.md).
"""

from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import Any

import yaml

TAG = "r2.18"
URL = f"https://raw.githubusercontent.com/UniversalDependencies/UD_English-EWT/{TAG}/en_ewt-ud-dev.conllu"
OUT = Path(__file__).resolve().parents[1] / "data" / "exercises"
PER_KIND = 8
EXCLUDED_RELATIONS = {"dep", "goeswith", "reparandum", "orphan", "list", "dislocated", "vocative"}
ALLOWED_PUNCT = {".", ",", "?", "!"}

# Relations offered in dependency exercises (gold relations are always added).
CORE_RELATIONS = [
    "nsubj",
    "nsubj:pass",
    "obj",
    "iobj",
    "obl",
    "advmod",
    "amod",
    "det",
    "case",
    "nmod",
    "nmod:poss",
    "aux",
    "aux:pass",
    "cop",
    "mark",
    "cc",
    "conj",
    "compound",
    "xcomp",
    "ccomp",
    "advcl",
    "acl",
    "acl:relcl",
    "nummod",
    "punct",
]


def sentences(text: str) -> list[tuple[dict[str, str], list[list[str]]]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = block.splitlines()
        meta = {
            k.strip(): v.strip()
            for k, _, v in (line[2:].partition("=") for line in lines if line.startswith("# "))
        }
        rows = [line.split("\t") for line in lines if line and line[0].isdigit()]
        out.append((meta, rows))
    return out


def eligible(rows: list[list[str]]) -> bool:
    if any("-" in r[0] or "." in r[0] for r in rows):
        return False  # multiword tokens or empty nodes
    words = rows
    if not 5 <= len(words) <= 10:
        return False
    if any("Typo=Yes" in r[5] for r in words):
        return False
    if any(r[7] in EXCLUDED_RELATIONS for r in words):
        return False
    if any(r[3] == "PUNCT" and r[1] not in ALLOWED_PUNCT for r in words):
        return False
    if sum(r[3] == "PUNCT" for r in words) > 1:
        return False
    if words[0][1][0].islower() or words[-1][3] != "PUNCT":
        return False  # prefer complete, capitalized sentences
    if any("Abbr=Yes" in r[5] for r in words):
        return False
    root = next(r for r in words if r[6] == "0")
    # Complete clauses only: the root has an overt subject (web text has many fragments).
    if not any(r[6] == root[0] and r[7] in {"nsubj", "nsubj:pass"} for r in words):
        return False
    return any(r[3] == "VERB" for r in words)


def well_spaced(text: str) -> bool:
    return not any(f" {p}" in text for p in ALLOWED_PUNCT)


def exercise(kind: str, number: int, meta: dict[str, str], rows: list[list[str]]) -> dict[str, Any]:
    tokens = [
        {"id": int(r[0]), "form": r[1], "upos": r[3], "head": int(r[6]), "deprel": r[7]}
        for r in rows
    ]
    data: dict[str, Any] = {
        "id": f"ud-en-{kind}-{number:02d}",
        "kind": kind,
        "language": "en",
        "title": meta["text"],
        "difficulty": 1 if len(tokens) <= 6 else 2 if len(tokens) <= 8 else 3,
        "source": {
            "treebank": "UD_English-EWT",
            "release": TAG,
            "split": "dev",
            "sent_id": meta["sent_id"],
            "license": "CC BY-SA 4.0",
        },
        "tokens": tokens,
    }
    if kind == "dependency":
        gold = [t["deprel"] for t in tokens if t["deprel"] != "root"]
        data["relations"] = sorted(set(CORE_RELATIONS) | set(gold))
    return data


def main() -> None:
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = response.read().decode("utf-8")
    picked = [
        (meta, rows)
        for meta, rows in sentences(data)
        if "text" in meta and well_spaced(meta["text"]) and eligible(rows)
    ]
    # Spread the selection over the corpus, then sort each set from short to long.
    step = max(1, len(picked) // (2 * PER_KIND))
    spread = picked[::step][: 2 * PER_KIND]
    pos_set = sorted(spread[0::2], key=lambda s: len(s[1]))
    dep_set = sorted(spread[1::2], key=lambda s: len(s[1]))

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("ud-en-*.yaml"):
        old.unlink()
    for kind, chosen in (("pos", pos_set), ("dependency", dep_set)):
        for number, (meta, rows) in enumerate(chosen, start=1):
            item = exercise(kind, number, meta, rows)
            path = OUT / f"{item['id']}.yaml"
            path.write_text(
                "# Generated by scripts/build_learning_exercises.py from UD_English-EWT "
                f"{TAG} (CC BY-SA 4.0). Do not edit by hand.\n"
                + yaml.safe_dump(item, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
                newline="\n",
            )
    print(
        f"{len(picked)} eligible sentences; wrote {len(pos_set)} POS and "
        f"{len(dep_set)} dependency exercises"
    )
    for meta, rows in pos_set + dep_set:
        print(f"  {len(rows):2d} words  {meta['text']}")


if __name__ == "__main__":
    main()
