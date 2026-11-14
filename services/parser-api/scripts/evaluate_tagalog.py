"""Evaluate Tagalog spaCy pipelines on raw text against gold treebanks, with one scorer.

Runs SyntaxLab's own engine on each gold sentence's raw text and scores the result with
``syntaxlab_api.analysis.ud_score``. Treebanks are not bundled here (the regression fixture is a
subset). Download them into one directory first:

    UD_Tagalog-TRG, tag r2.18, tl_trg-ud-test.conllu
    UD_Tagalog-NewsCrawl, dev branch, tl_newscrawl-ud-test.conllu

    uv run python scripts/evaluate_tagalog.py --gold-dir <dir> --output results.json

Models come from .models/spacy (`syntaxlab-api download-models`). Results and their
interpretation: docs/research/nlp-model-evaluation.md.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from syntaxlab_api.analysis.ud_score import METRICS, GoldSentence, Score, read_conllu
from syntaxlab_api.engines.base import EngineContext
from syntaxlab_api.engines.spacy_engine import SpacyEngine
from syntaxlab_api.languages.config import load_languages_file
from syntaxlab_api.schemas.analysis import Capability, StructureKind
from syntaxlab_api.settings import Settings

DEPENDENCY = frozenset({StructureKind.DEPENDENCY})
#: Relations a Tagalog learner most needs to be right, scored with their full label.
WATCHED_RELATIONS = ("root", "nsubj", "obj", "obj:agent", "obl", "case", "nmod:poss", "det")
WHEELS = {
    "tl_calamancy_md": "ed8e18e09b7ac2664d97b05d0b66e638e4be20f2f2a96efea8a58693278d6b29",
    "tl_calamancy_lg": "c922c44f6bfadf01aa967dc15ae43ebd587750b717d4b6ad710162434791c220",
}


def lowercase_initial(text: str) -> str:
    """The experiment: analyze as if the sentence's first letter were lowercase."""
    return text[0].lower() + text[1:] if text and len(text[0].lower()) == 1 else text


def evaluate(engine: SpacyEngine, gold: list[GoldSentence], *, lowercase: bool) -> dict[str, Any]:
    score = Score()
    started = time.perf_counter()
    for sentence in gold:
        analyzed = lowercase_initial(sentence.text) if lowercase else sentence.text
        score.add(sentence, engine.analyze(analyzed, DEPENDENCY))
    elapsed = time.perf_counter() - started
    result: dict[str, Any] = {metric: round(score.f1(metric), 2) for metric in METRICS}
    result["sentences"] = score.sentences
    result["gold_words"] = score.gold_words
    result["exact_tokenization"] = score.exact_tokenization
    result["split_sentences"] = score.split_sentences
    result["relations"] = {
        relation: {
            "gold": score.relation_gold[relation],
            "precision": round(score.relation_scores(relation)[0], 1),
            "recall": round(score.relation_scores(relation)[1], 1),
        }
        for relation in WATCHED_RELATIONS
    }
    result["ms_per_sentence"] = round(1000 * elapsed / len(gold), 1)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="write the results as JSON")
    parser.add_argument("--model", action="append", choices=sorted(WHEELS), help="default: all")
    parser.add_argument(
        "--chosen-only", action="store_true", help="only the settings in languages.yaml"
    )
    parser.add_argument(
        "--no-abbreviations", action="store_true", help="leave out the abbreviation list"
    )
    args = parser.parse_args()

    settings = Settings()
    config = load_languages_file(settings.languages_file)
    base = next(lang for lang in config.languages if lang.code == "tl")
    gold = {
        "TRG": read_conllu((args.gold_dir / "tl_trg-ud-test.conllu").read_text(encoding="utf-8")),
        "NewsCrawl": read_conllu(
            (args.gold_dir / "tl_newscrawl-ud-test.conllu").read_text(encoding="utf-8")
        ),
    }
    results: dict[str, Any] = {}
    grid = (
        [(True, True)]
        if args.chosen_only
        else [(a, b) for a in (False, True) for b in (False, True)]
    )
    for model in args.model or WHEELS:
        sha256 = WHEELS[model]
        for keep_hyphens, split_sentences in grid:
            options = {
                **base.engine_options,
                "model": model,
                "wheel_url": f"https://huggingface.co/ljvmiranda921/{model}/resolve/main/{model}-any-py3-none-any.whl",
                "wheel_sha256": sha256,
                "keep_hyphenated_words": keep_hyphens,
                "split_sentences": split_sentences,
                "abbreviations": []
                if args.no_abbreviations
                else base.engine_options["abbreviations"],
            }
            engine = SpacyEngine(
                EngineContext(
                    language="tl",
                    options=options,
                    schemes={Capability.DEPENDENCY: "ud-2"},
                    models_dir=settings.models_dir,
                )
            )
            engine.load()
            for lowercase in (False,) if args.chosen_only else (False, True):
                for name, sentences in gold.items():
                    key = " | ".join(
                        [
                            name,
                            model.removeprefix("tl_calamancy_"),
                            "keep-hyphens" if keep_hyphens else "default-tokenizer",
                            "punct-split" if split_sentences else "no-split",
                            "lowercase-initial" if lowercase else "as-written",
                        ]
                    )
                    results[key] = evaluate(engine, sentences, lowercase=lowercase)
                    r = results[key]
                    print(
                        f"{key:70} "
                        + " ".join(f"{m}={r[m]:6.2f}" for m in METRICS)
                        + f" exact={r['exact_tokenization']}/{r['sentences']}"
                        + f" split={r['split_sentences']}"
                        + f" {r['ms_per_sentence']}ms",
                        flush=True,
                    )
            engine.close()
    if args.output:
        args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
