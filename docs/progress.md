# Progress Log

## Current status

**Phases 1–3 for English are complete and verified.** That covers the foundation, English
analysis, and interactive visualization. Filipino is deferred by product decision. Next:
Phase 7 (Earley Algorithm Lab engine), then Learn and Compare. See the
[implementation plan](implementation-plan.md).

## Completed

### 2026-10-21: Phases 1–3 (English)

- **Decisions approved:** MIT license, Hugging Face Spaces as the hosting target, git
  repository on `main`, Algorithm Lab engine before Learn. Filipino and the reviewer are
  deferred. New requirement: **adding languages must not need code changes.**
- **Backend** (`services/parser-api`):
  - FastAPI service on Python 3.12/uv.
  - Engine plug-in system via entry points, with a generic Stanza engine.
  - Languages and annotation schemes declared in YAML and cross-validated against the engine.
  - Per-language worker thread, queue, timeout and cache.
  - Structural validation of every analysis.
  - Input normalization and limits, rate limiting, body-size limit, CORS.
  - Curated glossaries for UD relations, UPOS, UD features (Leipzig glosses) and Penn Treebank
    labels, served per scheme.
  - CLI for model download, config check and OpenAPI export.
- **Frontend** (`apps/web`):
  - Analyzer with constituency tree (textbook layout, triangle collapse) and dependency graph,
    both with zoom, pan, fit, reset and keyboard navigation.
  - Interlinear strip, inspector with source labels and provenance, SVG/PNG export with
    embedded font subsets.
  - Responsive panels on mobile. Typed API client generated from OpenAPI.
- **Verified:**
  - Backend: 138 unit/API tests; ruff and mypy --strict clean.
  - 5 real-model regression tests: UD EWT gold sample, overall LAS 94.1.
  - Frontend: 38 Vitest tests; ESLint and tsc clean; production build succeeds.
  - 19 Playwright E2E tests pass (desktop and mobile; 1 skipped by design).
  - Manually exercised in the browser against the live API: tree, collapse, dependency view,
    arc and word selection, mobile panels.
- **Findings recorded:**
  - The dependency and constituency models can disagree on PP attachment. This is documented
    in the language notes and on the About page.
  - Thread oversubscription slows Stanza 3–5×.

### 2026-10-21: Phase 0 (research)

See `docs/research/*` and `implementation-plan.md`.

## Known issues

- Latency was measured only on a heavily loaded dev laptop (0.9–4.7 s per sentence). It must
  be measured on the deployment host.
- Stanza memory figures are Windows working-set values; re-measure as private bytes or USS.
- `next/font` preloads italic and extended-Latin font files that are not needed at first paint
  (dev console warnings only).
- CI workflow is written but has not run yet (no remote repository).
- Deployment (Dockerfile, Hugging Face Space, Vercel) is not done yet.
- UD_Tagalog-NewsCrawl is not in an official UD release. Recheck its status before enabling
  Filipino.

## Next steps

1. Phase 7: Earley engine (Python) with trace, packed forest, grammar validator; then the
   Algorithm Lab UI.
2. Phase 6: Learn. POS and dependency exercises from UD gold; bracketing checked against all
   Earley parses.
3. Phase 5: Compare (meaningful once a second language is enabled).
4. Phase 8: Docker image, Hugging Face Space, Vercel, host measurements, accessibility audit.
