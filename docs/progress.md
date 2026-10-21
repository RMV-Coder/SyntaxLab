# Progress Log

## Current status

**Phases 1–3 (English), 6 (Practice), 7 (Algorithm Lab) and 8 (production readiness) are
complete and verified locally.** Going live needs accounts and decisions (repository, Hugging
Face plan, Vercel project): see [deployment.md](deployment.md). Filipino is deferred by product
decision; Compare follows once a second language is enabled. See the
[implementation plan](implementation-plan.md).

## Completed

### 2026-10-21: Phase 8 (production readiness), branch `phase-8-production`

- **API image** (`services/parser-api/Dockerfile`):
  - Two stages; dependencies from `uv.lock`; CPU-only torch.
  - Models are baked in at build time and checked by `syntaxlab-api check`.
  - Runs as non-root uid 1000 with one worker and a `/health` HEALTHCHECK.
- **Deployment** ([deployment.md](deployment.md)):
  - Hugging Face Space template (`deploy/huggingface/`). `prepare-space.sh` copies only
    tracked service files; tested locally, it produced a 759 KB checkout with no venv or
    models.
  - Vercel settings, post-deploy checks, and Cloud Run / Fly alternatives.
  - Measured web bundle sizes.
  - Hugging Face facts were checked against its current docs. **Creating Docker Spaces now
    needs a paid plan.**
- **Security:**
  - Web: static CSP, `nosniff`, `Referrer-Policy`, `X-Frame-Options`, `Permissions-Policy`.
  - API: `nosniff`, `no-referrer`, `X-Frame-Options`, explicit `Cache-Control` (errors never
    cacheable).
  - **Bug found:** with `--forwarded-allow-ips='*'`, uvicorn takes the client-written
    leftmost `X-Forwarded-For` entry, so the rate limit could be bypassed (reproduced). The
    image now trusts only private proxy ranges, and the API's own `X-Forwarded-For` option,
    which had the same flaw, was removed.
- **Accessibility:** axe audit (WCAG 2.2 A/AA) of every page in its main states, desktop and
  phone. Fixed:
  - tabs without panels, now toggle buttons;
  - contrast of inactive views and of text on the highlighter;
  - dependency-token names that did not match their visible text;
  - scrollable panels the keyboard could not reach.
- **Errors:** route and global error boundaries and a not-found page. Lab grammar-check and
  preset failures are now shown, where before they were silently dropped. A 2xx response
  that is not JSON is now an error rather than data.
- **Performance:** Radix Tooltip moved out of the root layout. About drops from 207 to 188 KB
  gzip and Practice from 239 to 222 KB.
- **CI:** `workflow_dispatch` added. A new `image` job builds the image, waits for `/ready`,
  parses a sentence, and reports image size and memory. actionlint is clean.
- **Verified:**
  - 238 backend tests; ruff and mypy --strict clean; 5 real-model regression tests.
  - 69 Vitest tests.
  - Playwright: 58 of 60 pass (30 × 2 viewports) against the production build with the CSP
    active. The other 2 are keyboard tests skipped on the phone by design.
  - In each of the last two full runs, one different test failed once and passed on retry.
    Both failures were runner-level (`Unexpected end of JSON input` with no stack, after a
    mocked response). Neither could be reproduced in 74 targeted repeats.

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
- The API is not live yet. Host chosen: Oracle Cloud Always Free Arm VM (`deploy/oracle/`,
  steps in [deployment.md](deployment.md#2-oracle-cloud-always-free-arm-vm-api-chosen)).
  The account, VM, DuckDNS hostname and VCN rules are manual steps. Until they are done, the
  live web app at https://syntaxlab-nine.vercel.app cannot analyze.
- Oracle may reclaim idle Always Free instances. The VM is sized (2 OCPU / 4 GB) so the
  API's memory use stays above the 20% idle line. Check the memory metric after the first
  week.
- Occasional one-off E2E failure inside the Playwright runner under heavy local load (see
  Phase 8). It passes on retry, and CI allows one retry. Investigate if it shows up in CI.
- A screen-reader pass by a person has not been done. Automated audits cover only part of
  WCAG.
- UD_Tagalog-NewsCrawl is not in an official UD release. Recheck its status before enabling
  Filipino.

## Next steps

1. Go live: push to GitHub (first CI run, including the image job), create the Space and
   the Vercel project, and measure on the host.
2. Phase 4: Filipino (Tagalog) via a spaCy engine plug-in for calamanCy, when a reviewer is
   available.
3. Phase 5: Compare (meaningful once a second language is enabled).
