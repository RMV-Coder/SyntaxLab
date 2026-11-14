"""Build the Tagalog linguistic-regression fixtures from UD treebanks (gold annotations).

Sentences are *selected*, never written: every reference analysis is the treebank's manual
annotation, copied unchanged. The selection is deterministic:

    uv run python scripts/build_tl_regression.py

Sources (CC BY-SA 4.0, see the fixture README):
- UD_Tagalog-TRG, tag r2.18: every sentence (grammar-book examples, held out from the model).
- UD_Tagalog-NewsCrawl, pinned dev commit, test split: every 8th sentence of 5-25 words.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ud"
BASE = "https://raw.githubusercontent.com/UniversalDependencies"
TRG_URL = f"{BASE}/UD_Tagalog-TRG/r2.18/tl_trg-ud-test.conllu"
NEWSCRAWL_COMMIT = "5b961422a0273d054b66bbc1ddb12b4338428aa3"
NEWSCRAWL_URL = f"{BASE}/UD_Tagalog-NewsCrawl/{NEWSCRAWL_COMMIT}/tl_newscrawl-ud-test.conllu"
EVERY_NTH = 8
MIN_WORDS, MAX_WORDS = 5, 25


def fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 - fixed URLs above
        return str(response.read().decode("utf-8"))


def word_count(block: str) -> int:
    return sum(line.split("\t", 1)[0].isdigit() for line in block.splitlines() if line)


def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    trg = fetch(TRG_URL).strip()
    (FIXTURES / "tl_trg_regression.conllu").write_text(trg + "\n", encoding="utf-8", newline="\n")

    blocks = fetch(NEWSCRAWL_URL).strip().split("\n\n")
    candidates = [b for b in blocks if MIN_WORDS <= word_count(b) <= MAX_WORDS]
    selected = candidates[::EVERY_NTH]
    (FIXTURES / "tl_newscrawl_regression.conllu").write_text(
        "\n\n".join(selected) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"TRG: {trg.count('# sent_id')} sentences")
    print(f"NewsCrawl: {len(selected)} of {len(blocks)} sentences")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
