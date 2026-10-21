# Progress Log

## Current status

**Phases 1–3 (English), 6 (Practice) and 7 (Algorithm Lab) are complete and verified.**
Filipino is deferred by product decision. Next: Phase 8 (deployment and production readiness),
then Compare once a second language is enabled. See the [implementation plan](implementation-plan.md).

## Completed

### 2026-10-21: Phase 6 (Practice), branch `phase-6-learn`

- **Exercise bank** (`data/exercises/`):
  - 8 part-of-speech and 8 dependency exercises generated from UD English-EWT r2.18 dev
    gold. The script uses deterministic rules (complete clauses, 5–10 words, no typos,
    abbreviations or special relations) and the files carry CC BY-SA 4.0 attribution.
  - 4 tree-building exercises on the preset grammars, two of them ambiguous.
  - All validated at startup.
- **Checking** (`learning/checking.py`):
  - POS and dependency answers compared per word with gold; a matching base relation counts
    as partial.
  - Trees compared with **every** Earley parse (ε removed). Feedback is relative to the
    closest parse and separates missing, other-reading and unlicensed constituents. Each node
    is checked against the grammar's rules, and the exact missing rule is named.
- **API:** list exercises, exercise detail (never includes the answer key), check.
- **Frontend** (`/learn`, header "Practice"):
  - An exercise list with per-browser progress.
  - Tagging with native selects and definitions in the feedback.
  - Word relations with a live graph and the annotated graph for comparison.
  - A span-based tree builder: crossing prevention, unary-chain reordering, undo, live
    preview, and a correct tree on request.
- **Verified:**
  - 237 backend tests, including every parse of every tree exercise being accepted (in
    shuffled order) and every feedback category.
  - 68 Vitest and 46 Playwright tests (2 skipped by design); manual browser checks against
    the live API.
- **Issues found and fixed:**
  - Next 16 `cacheComponents` requires request-time data (`params`, `usePathname`) inside
    Suspense. The header navigation and the exercise page were restructured, and the build
    now partially prerenders `/learn/[id]`.
  - The first selection of UD sentences included web-text fragments; the selection rules were
    tightened.
  - Rule feedback was withheld whenever any problem existed; now only crossing brackets block
    it.


### 2026-10-21: Phase 7 (Algorithm Lab), branch `phase-7-algorithm-lab`

- **Backend** (`syntaxlab_api/grammar/`):
  - Grammar notation with line-numbered diagnostics, including cycle detection (infinite
    ambiguity), undefined, unproductive and unreachable symbols, and limits.
  - Earley parser with Aycock–Horspool nullable handling, a full event trace, and derivation
    links forming a packed forest. Exact tree counts by dynamic programming; lazy tree
    enumeration.
  - Four data-driven preset grammars whose example outcomes are verified by tests.
  - Endpoints for presets, validate and parse.
- **Frontend** (`/lab`):
  - Grammar editor with live validation, and examples showing their verified outcomes.
  - Replay controls: reset, step back and forward, play/pause, speed, scrubber, and keyboard
    shortcuts that keep working when the focused control is disabled.
  - Plain-language explanation of every event. Chart view with the new item highlighted, its
    cause outlined, and dead ends struck through.
  - The outcome is revealed at the end of the replay. Every parse tree is shown, and each node
    links to the step that completed it. Mobile panels.
- **Verified:**
  - 209 backend tests, including an independent brute-force oracle that must produce exactly
    the same trees, Catalan-number counts, exhaustive ε-rule cases, and trace replay integrity.
  - 55 Vitest tests and 34 Playwright tests (desktop and mobile; 2 skipped by design).
  - Manually exercised in the browser on desktop and phone sizes.
- **Bugs found and fixed while verifying:**
  - The root of an all-empty parse kept a placeholder position (caught by the oracle).
  - Shortcuts stopped working after the focused button became disabled.
  - The step slider's accessible name was "0".
  - Phone layouts scrolled sideways because the grid column grew to the chart's width (also
    latent in the Analyzer; now covered by an E2E check).


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

1. Phase 8: Docker image, Hugging Face Space, Vercel, host measurements, accessibility audit,
   first CI run on a remote repository.
2. Phase 4: Filipino (Tagalog) via a spaCy engine plug-in for calamanCy, when a reviewer is
   available.
3. Phase 5: Compare (meaningful once a second language is enabled).
