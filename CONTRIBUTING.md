# Contributing to SyntaxLab

Thanks for helping. SyntaxLab is judged by whether its analyses are linguistically meaningful
and honest, so contributions are held to that standard as much as to code quality.

## Ground rules

- **Never fabricate linguistic data.** Reference trees and test expectations come from
  annotated treebanks (see `services/parser-api/scripts/build_en_regression.py`), never from
  intuition or an LLM.
- **No silent fallbacks.** If a language or engine cannot do something, raise a typed error.
  Do not substitute another language, another representation, or a sample.
- **Don't change parser output to look nicer.** Normalization belongs in engines, must be
  documented, and must be measured against gold data.
- **Don't claim support without evaluation.** New languages follow
  [docs/adding-a-language.md](docs/adding-a-language.md), including recorded accuracy and
  limitations.
- Curated definitions cite the annotation guidelines they paraphrase.

## Workflow

1. Read [docs/development.md](docs/development.md) to set up.
2. Make a focused change with tests.
3. Before opening a pull request, run:
   ```bash
   pnpm lint && pnpm typecheck && pnpm test && pnpm test:e2e
   ```
   If you changed Pydantic schemas, also run `pnpm api:types` and commit the generated files.
   If you touched an engine or normalization, also run
   `cd services/parser-api && uv run pytest -m models`.
4. Update the docs affected by your change: `docs/api.md`, the limitations, and
   `docs/progress.md`.

## Style

- Python: ruff (lint + format), mypy --strict, typed Pydantic models for every boundary.
- TypeScript: strict mode, ESLint with React Compiler rules, derived state over syncing
  effects.
- UI copy: sentence case, plain verbs, errors that say what happened and what to do.

## Licensing

Code contributions are MIT. Treebank-derived data stays under its original license (e.g. CC
BY-SA 4.0) in its own directory, with attribution.
