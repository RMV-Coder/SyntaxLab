# Implementation Plan

Status: **Approved 2026-10-21** (with Filipino deferred). Phases 1–3 for English are done; see `progress.md`.
Inputs: `docs/architecture.md`, `docs/research/*`.

## 1. MVP scope

### In scope

| Area | MVP content |
|---|---|
| Analyzer | English: UD dependency + PTB constituency + POS/lemma/features. Filipino (Tagalog): UD dependency + POS/lemma/features. One sentence per analysis. Sample sentences. Parser provenance and warnings |
| Visualization | Constituency tree (collapse/expand, zoom/pan/fit/reset, hover, click → explanation). Dependency arcs (token select, highlight, label toggle). SVG and PNG export. Accessible table view |
| Explanations | Curated glossary: UPOS, UD deprels, UD features, PTB labels. Tagalog-specific notes marked "Draft, pending review" until reviewed |
| Compare | Two independent analyses side by side, plus observation panel computed only from the two results (word order of predicate/arguments, case-marker tokens, voice/aspect features present, label inventory differences). No equivalence claims |
| Algorithm Lab | Earley parser with replayable trace (play/pause/step ±/reset), state inspector, parse forest → all trees (capped), grammar editor + validator, preset toy grammars |
| Learn | (1) POS tagging and (2) dependency head/label exercises on **gold UD sentences** (EWT, TRG, NewsCrawl test). (3) Constituency bracketing exercises checked against **all parses of an explicit toy grammar** |
| Quality | pytest, Vitest + RTL, Playwright critical paths, golden linguistic regression, GitHub Actions |

### Out of scope (MVP)

Code-switching, Cebuano/Spanish/Japanese, Filipino constituency, LLM explanations, user
accounts and database, CYK, automatic translation/alignment, k-best parser output, confidence
scores.

## 2. Phase order and effort

The order is adjusted from the brief: the **Earley engine (Phase 7 core) moves before Learn**,
because constituency exercises are checked against it. Estimates are focused engineering days
for one developer pairing with me. They are estimates, not commitments.

| # | Phase | Key outputs | Est. days | Depends on |
|---|---|---|---|---|
| 1 | Foundation | Monorepo, Next.js 16 + Tailwind 4 + shadcn, FastAPI on Py 3.12 via uv, ruff/mypy/eslint/tsc, pytest/vitest/playwright skeletons, OpenAPI → TS codegen, CI skeleton, README | 2–3 | n/a |
| 2 | English analysis | Adapter protocol, registry, EnglishAdapter (Stanza), normalizer + constituency validator, `/parse`, `/languages`, `/health`, `/ready`, concurrency/limits, EWT-based golden tests, eval script committed | 3–4 | 1 |
| 3 | Visualization | Dependency + constituency renderers, interactions, export, glossary + explanation panel, analyzer layout (desktop 3-pane, mobile tabs), a11y table view | 6–8 | 2 |
| 4 | Filipino | TagalogAdapter (calamanCy, hyphen fix), md-vs-lg + capitalization experiments, TRG/NewsCrawl golden tests, capability page, Tagalog glossary notes (draft) | 3–4 (+ external review time) | 2 |
| 5 | Compare | Side-by-side workspace, observation functions (pure TS, unit-tested), comparison tests | 3 | 3, 4 |
| 7 | Algorithm Lab | Earley + forest + trace (Python), grammar DSL + validator, `/grammar/*` endpoints, trace replay UI, algorithm test suite (incl. ambiguity, left recursion, ε, cycles) | 6–8 | 1 (UI needs 3) |
| 6 | Learn | Exercise bank (UD gold + grammar-based), POS / dependency / bracketing exercise UIs, checker + feedback, tests | 6–8 | 3, 4, 7 |
| 8 | Production readiness | Docker image, HF Spaces deploy + Vercel, measured latency/memory on host, a11y audit, error-handling audit, rate limits, docs finalization | 4–6 | all |
| | **Total** | | **33–44** | |

## 3. Highest-risk decisions and mitigations

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | **Filipino parser quality on textbook sentences is unknown.** Measured errors exist (aspect, ADJ→VERB, capitalization) | High | Measure on TRG (grammar-book style, gold). Show documented limitations in the UI. Never present model output as a teaching answer key. Exercises use gold only |
| R2 | **No Tagalog linguist on the project.** Teaching notes on voice/*ang* cannot be self-certified | High | Glossary notes marked "Draft, pending review". Fixtures only from treebank gold. A reviewer is needed before calling Phase 4 done |
| R3 | **Upstream fragility:** calamanCy is a single-maintainer project with stale dependency pins | Medium | `--no-deps` install with SHA-256 pins. Adapter isolates the library. Eval script detects regressions on upgrade |
| R4 | **CPU latency** of Stanza English: 0.9–1.9 s per sentence on the dev laptop | Medium | Thread pinning, LRU cache, pre-warmed samples, honest loading UI. Measure on the target host early (spike at end of Phase 2, not Phase 8) |
| R5 | **Free hosting** sleeps and policies change | Medium | Docker image is host-agnostic. The frontend handles "waking up" via `/ready`. Document a paid fallback (Cloud Run / Fly) |
| R6 | **PTB labels ≠ textbook labels** confuse English majors | Medium | Label-glossary mapping in the explanation panel ("PTB `NN` ≈ textbook N"), without relabelling the tree |
| R7 | **Licensing:** CC BY-SA share-alike for bundled gold data. Ugnayan is NC | Low–Med | Code MIT. `data/` directory CC BY-SA with attribution. Ugnayan not bundled |
| R8 | **Earley tree recovery** correctness under ambiguity/ε/cycles | Medium | Forest-based recovery, a brute-force cross-check oracle in tests (enumerate derivations for tiny grammars), cycle detection |

## 4. Decisions (resolved 2026-10-21)

1. MVP scope approved. **English first; Filipino deferred.** No Filipino constituency view.
2. Phase reordering approved (Algorithm Lab engine before Learn).
3. License: MIT for code. Bundled treebank data stays CC BY-SA 4.0 in its own directory.
4. Hosting: Hugging Face Spaces (Docker) for the API, Vercel for the web app.
5. Tagalog reviewer: deferred together with Filipino.
6. Git repository initialized on `main`.
7. **New requirement:** adding a language must not need code changes. This is implemented as
   YAML configuration plus engine plug-ins, and covered by tests.

## 5. Initial task checklist

### Phase 0: Research (this deliverable)
- [x] Inspect repository (empty, greenfield)
- [x] Verify English parser availability and quality (Stanza 1.15, measured on EWT)
- [x] Verify Filipino resources (NewsCrawl, TRG, Ugnayan, calamanCy, Stanza has no tl)
- [x] Measure calamanCy accuracy, memory, latency; verify train/test separation
- [x] Identify and measure the hyphen tokenization defect and fix
- [x] Evaluate Earley vs. CYK
- [x] Architecture proposal, capability matrix, risks, plan
- [x] Architectural review and approval

### Phase 1: Foundation
- [ ] `git init`, `.gitignore`, LICENSE, README skeleton, CONTRIBUTING
- [ ] `apps/web`: Next.js 16 (App Router, TS strict), Tailwind 4, shadcn/ui, Lucide, ESLint
- [ ] `services/parser-api`: uv project, Python 3.12 pin, FastAPI, Pydantic, ruff, mypy, pytest
- [ ] OpenAPI export + `openapi-typescript` codegen + staleness check
- [ ] Root dev scripts (run both, test both)
- [ ] CI: lint, typecheck, unit tests, build (no model downloads in the PR path)

### Phase 2: English analysis
- [ ] Schemas (Analysis, Token, DependencyArc, ConstituencyNode, Provenance, Warning, errors)
- [ ] Adapter protocol, registry, capability model
- [ ] EnglishAdapter + normalizer (Stanza → schema), constituency validator
- [ ] Concurrency: per-model executor, lock, queue bound, timeout, thread pinning, LRU cache
- [ ] Endpoints `/api/v1/languages`, `/api/v1/languages/{code}`, `/api/v1/parse`, `/health`, `/ready`
- [ ] Golden tests from EWT test gold (deprel/head agreement thresholds, not exact equality)
- [ ] Commit eval scripts. Latency spike on a 2-vCPU host

(Later phases expand into checklists when they start, and are tracked in `docs/progress.md`.)
