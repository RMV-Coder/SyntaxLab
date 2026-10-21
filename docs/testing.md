# Testing

Results below are from the last local run (2026-10-21, Windows 11, CPU only).

## Layers

| Layer | Tool | Location | Needs models | Count |
|---|---|---|---|---|
| Backend unit (validators, normalization, config, glossaries, input, rate limiting, grammars, Earley, exercises and answer checking) | pytest | `services/parser-api/tests/unit` | no | 185 |
| Backend HTTP (every error code, back-pressure, caching, readiness, CORS, security and cache headers, extensibility, Algorithm Lab, Practice) | pytest + TestClient | `services/parser-api/tests/api` | no | 53 |
| Linguistic regression | pytest `-m models` | `services/parser-api/tests/integration` | yes | 5 |
| Frontend unit (layouts, glossary lookup, selection, export, API client, Lab replay and explanations, tree builder, feedback wording, progress) | Vitest + jsdom | `apps/web/**/*.test.ts` | no | 69 |
| End-to-end (desktop and mobile), including the accessibility audit and security headers | Playwright | `apps/web/e2e` | no¹ | 30 × 2 viewports |

¹ E2E runs the real Next.js app. API calls are answered with **responses recorded from the
real parser** (`apps/web/e2e/fixtures`), so the suite is deterministic and needs no models. The
model-backed path is covered by the linguistic regression suite.

## Test doubles, and what they are not

`tests/support/engines.py` defines `WhitespaceTestEngine`, which produces structurally valid but
linguistically meaningless output. It exists only to test API plumbing (limits, errors,
queueing, caching). It is never configured in production and never used for linguistic
assertions.

Stanza normalization is unit-tested with hand-built Stanza `Document`/`Tree` objects, including
multiword tokens and malformed trees that must be rejected.

## Algorithm Lab correctness

`tests/unit/test_earley.py` checks the Earley parser against an **independent brute-force
oracle**, which enumerates all derivations over spans. It also checks known Catalan-number
ambiguity counts, ε-rule edge cases (exhaustively for all strings of up to 4 words), replay
integrity of the trace, and the expected outcome declared for every preset example. Details:
[parsing-algorithms.md](parsing-algorithms.md#how-correctness-is-checked).

E2E also checks that neither page scrolls sideways on a phone.

## Practice answer checking

`tests/unit/test_learning.py` builds an answer from **every** Earley parse of every tree
exercise, shuffles it, and requires each to be accepted, so a valid alternative reading can
never be rejected. It then exercises each feedback category with a minimal case: missing,
other reading, unlicensed, crossing, no root, uncovered word, unknown category, out of range,
a missing rule, and a unary chain in the wrong order. Empty rules are covered too: students may
leave out ε constituents. The E2E tree test's mock only returns "correct" if the UI posts
exactly the right labelled spans.

## Accessibility

`e2e/a11y.spec.ts` runs axe-core (`@axe-core/playwright`) against WCAG 2.0, 2.1 and 2.2 levels A
and AA. It audits every page in the states that matter, on desktop and phone sizes:

- the Analyzer when empty, with a node selected, and in the dependency view;
- the Lab with a grammar loaded, in the middle of a replay, and at the outcome;
- the Practice list and one exercise of each kind;
- About.

Any violation fails the test, and the failure lists each rule and element. The audit found
these issues, all now fixed:

- tab semantics without panels, replaced by a toggle group with `aria-pressed`;
- low contrast on inactive views and on text over the highlighter;
- dependency tokens whose accessible name did not include their visible text;
- scrollable side panels that the keyboard could not reach.

Automated checks cover part of WCAG. Keyboard paths (tree and graph navigation, Lab
shortcuts) have their own E2E tests. A screen-reader pass by a person has not been done yet.

## Security headers

`e2e/security.spec.ts` checks the web app's response headers (CSP, `nosniff`,
`Referrer-Policy`). It also records `securitypolicyviolation` events while analyzing, exporting
a PNG and opening the Lab, and requires there to be none. A probe confirmed that the recorder
catches real violations (an external image and an external `fetch`). The API's headers and its
cache rules (errors are never cacheable) are tested in `tests/api/test_api.py`.

## Linguistic regression

- **Gold data, not invented trees.** `tests/fixtures/ud/en_ewt_regression.conllu` holds 77
  sentences *selected* from the UD English-EWT r2.18 test split by deterministic rules over
  their gold annotations (`scripts/build_en_regression.py`). The categories are simple
  declaratives, questions, negation, passives, PPs, complex NPs, compound and complex
  sentences.
- Thresholds sit below measured scores, to catch regressions without flakiness: tokenization
  match ≥ 85%, overall LAS ≥ 0.85, per category LAS ≥ 0.75.
- A few uncontroversial facts about textbook sentences are asserted directly. For example,
  `obl:agent` for a passive *by*-phrase, which is the UD English convention, and `S → NP VP`.

Last run:

```
category               sents tok-mismatch   UPOS    UAS    LAS
ALL                       74            3  0.976  0.955  0.941
complex_noun_phrase       11            1  0.964  0.938  0.938
complex_sentence          37            1  0.970  0.969  0.953
compound_sentence         12            0  0.987  0.957  0.945
negation                  15            0  0.978  0.951  0.933
passive                   11            1  0.984  0.880  0.863
prepositional_phrase      49            2  0.975  0.946  0.933
question                  12            0  0.964  0.982  0.964
simple_declarative        14            0  0.972  0.991  0.981
```

## Running

```bash
cd services/parser-api && uv run pytest                 # unit + API
cd services/parser-api && uv run pytest -m models -s    # real models (download first)
cd apps/web && pnpm test                                # Vitest
cd apps/web && pnpm test:e2e                            # Playwright (dev server)
cd apps/web && pnpm build && CI=1 pnpm test:e2e         # Playwright against a production build
```

On heavily loaded machines Vitest's default fork pool can time out starting workers. The
config therefore uses `pool: "threads"`. Even so, a run on an overloaded machine can
occasionally report "no tests". That run exits non-zero, so it can never pass silently; rerun
it.

## CI

`.github/workflows/ci.yml`:

- **api**: ruff, mypy, pytest with coverage.
- **contract**: regenerates OpenAPI and TypeScript types and fails on any diff.
- **web**: ESLint, tsc, Vitest, production build, Playwright.
- **models**: downloads the models (cached) and runs the linguistic regression on pushes to
  `main`.

No secrets are required.
