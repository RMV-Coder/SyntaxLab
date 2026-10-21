# Development

## Requirements

- Node.js ≥ 20.9 (developed on 24) and pnpm 10 (`corepack enable`)
- [uv](https://docs.astral.sh/uv/). The API pins **Python 3.12** (`.python-version`) and uv
  installs it automatically, whatever your system Python is. 3.12 is used because the
  researched Filipino models depend on libraries without newer wheels; see
  `docs/research/nlp-model-evaluation.md` §3.6.
- About 1 GB of disk for the Python environment (CPU-only torch) and about 430 MB for the
  English models.

## Layout

```
apps/web/                 Next.js app (pnpm workspace package "web")
  app/                    routes
  features/analyzer/      Analyzer UI (diagrams, interlinear strip, inspector, hooks)
  lib/api/                generated OpenAPI types + typed client
  lib/syntax/             pure layout and glossary logic (unit-tested)
  lib/export/             SVG/PNG export
  e2e/                    Playwright tests and recorded API fixtures
services/parser-api/      FastAPI service (uv project)
  config/languages.yaml   languages (the only place they are declared)
  data/glossary/          curated label explanations, one file per annotation scheme
  src/syntaxlab_api/      application
  tests/                  unit, api, integration (real models), fixtures
docs/                     architecture, API, research, guides
```

## Running locally

```bash
pnpm install
cd services/parser-api
uv sync --extra stanza                      # API + Stanza engine + dev tools
uv run syntaxlab-api download-models        # into services/parser-api/.models (git-ignored)
uv run syntaxlab-api check --load           # validate config and load models once
cd ../..
pnpm dev:api                                # http://127.0.0.1:8710, auto-reload
pnpm dev:web                                # http://localhost:3000
```

The web app reads the API URL from `NEXT_PUBLIC_SYNTAXLAB_API_URL` (default
`http://127.0.0.1:8710`). It is inlined at build time.

Port 8710 is used for the API so it does not collide with the common 8000.

Set `SYNTAXLAB_CPU_THREADS` to your physical core count or fewer. Thread oversubscription
made Stanza 3–5× slower in our measurements.

## Common tasks

| Task | Command |
|---|---|
| Lint everything | `pnpm lint` |
| Type-check everything | `pnpm typecheck` |
| Unit and API tests | `pnpm test` |
| E2E (builds nothing; uses `next dev`) | `pnpm test:e2e` |
| Regenerate API types after changing Pydantic schemas | `pnpm api:types` |
| Real-model linguistic regression | `cd services/parser-api && uv run pytest -m models -s` |
| Rebuild the English regression fixture from UD EWT | `uv run python scripts/build_en_regression.py` |
| Add a language | see [adding-a-language.md](adding-a-language.md) |

## Conventions

- The backend is strictly typed (`mypy --strict`) and linted/formatted with ruff.
- The frontend uses strict TypeScript and ESLint with the React Compiler rules. Prefer derived
  state over effects that set state.
- SVG diagrams use literal colour values from `lib/theme.ts` (not CSS variables), so exported
  files look the same outside the app. Keep them in sync with `app/globals.css`.
- Never hard-code a language in the client. Read languages, capabilities and schemes from the
  API.
