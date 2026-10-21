# SyntaxLab Architecture

Status: **English analyzer (Phases 1–3), Practice (Phase 6) and Algorithm Lab (Phase 7)
implemented.** Filipino and Compare are designed but not built. Last updated 2026-10-21.

## 1. Principles that shape the architecture

1. Every analysis comes from an identified component, never from an LLM or a hard-coded
   sample. Provenance travels with every response.
2. Languages differ in capabilities, and the system models that explicitly. Each language
   declares what its engine produces; clients render only what is declared; requests for
   anything else are refused, **never substituted**.
3. **Adding a language is configuration, not code**: a YAML entry plus, if needed, an engine
   plug-in. See [adding-a-language.md](adding-a-language.md).
4. Stateless service; no database.

## 2. System overview

```
Browser: Next.js 16 app (React 19, Tailwind 4, shadcn/ui)
  │  Analyzer: input │ diagram canvas (constituency / dependency) + interlinear strip │ inspector
  │  React renders SVG; d3-zoom maintains the pan/zoom transform; pure layout functions
  │  Typed client generated from OpenAPI
  ▼  HTTPS/JSON
Parser API: FastAPI, Python 3.12, one process
  ├─ middleware: body-size limit, CORS; rate limiter (token bucket per client)
  ├─ input normalization: NFC, control/bidi rejection, length/word limits
  ├─ LanguageRegistry  ◄── config/languages.yaml (languages, schemes, samples, notes, limits)
  │    └─ LanguageRuntime per language:
  │         dedicated worker thread (load + inference), bounded queue, timeout, LRU cache
  │         └─ Engine plug-in (entry point "syntaxlab.engines"): built-in StanzaEngine, …
  ├─ structural validation of every analysis (analysis/validate.py)
  ├─ glossaries per annotation scheme ◄── data/glossary/<scheme>.yaml
  └─ /health, /ready
```

## 3. Repository layout

See [development.md](development.md#layout).

## 4. Engines (the extension point)

`src/syntaxlab_api/engines/base.py`:

```python
class Engine(ABC):
    name: ClassVar[str]                          # entry-point name, e.g. "stanza"
    def __init__(self, context: EngineContext)   # language, options, schemes, threads, models dir
    def capabilities(self) -> Mapping[Capability, str]   # computable without loading models
    def download(self) -> None                   # CLI/build time only
    def load(self) -> None                       # on the language's worker thread
    def analyze(self, text, structures) -> list[SentenceAnalysis]
    def close(self) -> None
```

- Engines are discovered through the `syntaxlab.engines` entry-point group, so any installed
  package can contribute one. A `module:Class` reference also works.
- `StanzaEngine` is generic. Its capabilities follow its configured processor list, so the same
  class serves any Stanza language.
- The contract (faithful output, no derived structures, no fabricated alternatives or scores,
  `EngineError` on failure) is enforced by `analysis/validate.py` on every response and by the
  tests.

## 5. Language configuration

`config/languages.yaml` declares the annotation schemes (id, name, URL) and the languages. For
each language it gives the engine, engine options, the scheme of each layer, limits, samples,
and notes. Startup validation cross-checks configuration against the engine:

- every structure the engine produces must name its scheme, and
- no scheme may be claimed for a layer the engine does not produce.

Codes and aliases are unique and case-insensitive.

## 6. Model lifecycle and concurrency

- One Uvicorn worker, because each extra worker duplicates every model in memory.
- Each language has a **single-thread executor**. The engine loads and runs on that thread, so
  inference is serialized (pipelines are not documented as thread-safe), and FIFO order means
  the load always completes before the first analysis.
- Models preload at startup by default (`SYNTAXLAB_PRELOAD`). `/ready` returns 503 until every
  language is ready; `/health` responds immediately.
- Back-pressure: at most `MAX_QUEUE` pending analyses per language, otherwise **503
  `overloaded`** with `Retry-After`. There is a per-request timeout (**504**), and an LRU
  cache keyed on (NFC text, structures).
- `torch.set_num_threads(CPU_THREADS)`: oversubscription measured 3–5× slower.

**Measured** on a dev laptop (6 cores, 1.2 GHz base, CPU only, heavily loaded):

- Stanza English (depparse + constituency) uses about 650 MB of working set.
- Warm latency is 0.9–4.7 s per sentence.
- Cold load is 6–80 s.

Deployment-host numbers are still to be measured.

## 7. Analysis schema

Full reference in [api.md](api.md). Key decisions:

- Tokens are 1-based syntactic words. Multiword tokens (*don't* → *do* + *n't*) are kept, so
  surface text is recoverable.
- Engine-specific values (XPOS, raw features) are preserved, not discarded.
- Constituency trees are flat node lists with explicit children, pre-terminal `token_id`s, and
  spans. Dependency arcs use `head = 0` for the root.
- Structural invariants are validated server-side; a violation is an error, never repaired.
- No confidence field. Neither engine exposes calibrated scores.
- No `alternatives` field yet. The statistical parsers return one analysis (greedy spaCy
  parser, no k-best in Stanza; verified). Alternatives will come from the Earley engine, with
  its own schema.

## 8. Explanations

- Curated glossaries live in `data/glossary/<scheme>.yaml` and are served by
  `GET /api/v1/schemes/{id}`, keyed by **annotation scheme**. UD glossaries therefore serve
  every UD language; per-language caveats go in `language_notes`.
- Shipped: `ud-2` (54 relations: the universal set plus English subtypes), `ud-upos` (17, with
  POS families used for colour), `ud-feats` (Leipzig gloss abbreviations, flagged where
  non-standard), and `ptb-revised` (79 labels, with approximate textbook equivalents).
- Validated at startup. Coverage tests check them against the gold data and against the
  Leipzig Glossing Rules list.
- The UI marks every section as **Parser output** or **Curated definition**. A UD subtype
  without its own entry is explained through its base relation, and the UI says so. There are
  no AI-generated explanations.

## 9. Frontend

- React owns the DOM; D3 is used only for `d3-zoom`. Layouts are pure functions
  (`lib/syntax/*-layout.ts`) with an injected text-measuring function, so they are
  unit-testable.
- **Constituency:** textbook layout. Words sit on one baseline, each phrase is centred over its
  first and last child, and collapsed phrases use the triangle notation. Collapse via the
  inspector, a double-click, or the C key.
- **Dependency:** arcs are nested by span containment, outgoing arcs on the same side are
  staggered, and there is a root marker. Crossing arcs are drawn as they are, not hidden.
- One selection model is shared by every view: a word, a phrase, or an arc. The tree, arcs,
  interlinear strip and inspector all highlight the same thing.
- Accessibility:
  - Roving tabindex with arrow keys that follow tree edges (or head/dependent links).
  - Accessible names on every node.
  - The interlinear strip is a real `<table>`, plus a bracket-notation text alternative.
  - `lang` is set from the analyzed language.
  - Reduced motion is respected, and focus is always visible.
- Export serializes the full diagram, independent of zoom. Only the font subsets covering the
  diagram's characters are embedded. PNG is rendered at 2×.
- Responsive: three columns at ≥1024 px; below that, Sentence / Diagram / Details panels.

## 9a. Algorithm Lab

- `syntaxlab_api/grammar/`:
  - `grammar.py`: notation, parsing, validation (cycles, undefined/unproductive/unreachable
    symbols, limits), nullable set.
  - `earley.py`: recognizer with Aycock–Horspool nullable handling, trace events, derivation
    links (packed forest), exact counting, lazy enumeration.
  - `presets.py`: data-driven preset grammars with verified example outcomes.
- The parse endpoint is a sync handler, so it runs in FastAPI's thread pool. Bounded inputs
  keep it fast (the largest preset example takes under 200 events). It is rate-limited like
  `/parse`.
- The frontend replays the trace (`features/lab/replay.ts`) without simulating anything.
  Chart, explanations, controls and trees are separate components. Derivation trees have their
  own layout (`lib/syntax/derivation-layout.ts`), because grammars may place words inside any
  rule and may derive ε.
- Full description: [parsing-algorithms.md](parsing-algorithms.md).

## 9b. Practice (Learn)

- `data/exercises/*.yaml`:
  - POS and dependency exercises are generated from UD English-EWT gold by
    `scripts/build_learning_exercises.py`, using deterministic selection rules.
  - Tree exercises name a preset grammar and a sentence.
  - All are validated at startup: gold trees must be well-formed, and grammars must generate
    their sentences.
- `learning/checking.py`:
  - POS and dependency answers are compared per word with gold. A base relation matching a
    subtype counts as partial.
  - Constituency answers are nested by containment (identical spans: earlier dominates) and
    compared exactly with every Earley parse, with ε removed. The closest parse by labelled-span
    F1 drives the feedback, and every node is checked against the grammar's rules (nullable
    symbols may be omitted).
- The exercise detail endpoint never includes the answer key. The check response does.
- Frontend (`/learn`):
  - Native selects for tags, heads and relations.
  - A live dependency graph reusing the Analyzer renderer.
  - A span-based tree builder (`tree-builder-model.ts`: crossing and duplicate prevention,
    unary-chain reordering, undo) with a live preview using the Lab's derivation layout.
  - Progress kept in `localStorage` only (no accounts, D6).
- `/learn/[id]` reads its param inside `<Suspense>` and the header's active-link navigation is
  in its own Suspense boundary, as `cacheComponents` requires. The route is partially
  prerendered.

## 10. Security

- Input: NFC normalization; control, surrogate and bidi-override characters are rejected;
  character, word and sentence limits apply; the body is capped at 16 KB.
- User text is rendered only as React/SVG text nodes, and export goes through XMLSerializer,
  which escapes it.
- CORS is restricted to configured origins. Validation errors never echo submitted values;
  error messages never contain exception text.
- Rate limiting is per client. `X-Forwarded-For` is honoured only if
  `TRUST_PROXY_HEADERS=true`.
- Glossaries are served only for schemes declared in configuration. Ids are pattern-checked,
  so there is no path traversal.

## 11. Decisions log

| # | Decision | Reason |
|---|---|---|
| D1 | Backend on Python 3.12 (uv-managed) | Verified for every researched model. calamanCy's stale `spacy-transformers` pin blocks 3.14 for its transformer model |
| D2 | Stanza for English dependency + constituency | Same tokenization for both views, UD labels, maintained. benepar is unmaintained since 2021 |
| D3 | Filipino deferred (calamanCy researched, not enabled) | Per product decision. Research and tokenizer fix are documented for when it is enabled |
| D4 | No Filipino constituency | No treebank or parser exists, and Tagalog phrase structure is contested |
| D5 | Earley (not CYK) for the future Algorithm Lab | Works on the student's grammar unchanged, with honest step explanations |
| D6 | No database | Stateless MVP |
| D7 | No confidence scores, no LLM explanations | Not provided by the models; LLM output is not authoritative |
| D8 | Languages and engines as configuration/plug-ins | Adding a language must not require code changes (product requirement) |
| D9 | Glossaries keyed by scheme, served by the API | Explanations follow the annotation scheme, not the language; new languages reuse them |
| D10 | Test engine and recorded fixtures for non-model tests | Deterministic CI without 430 MB downloads; linguistic behaviour tested on real models separately |
| D11 | API on port 8710 | Avoids collisions with the common 8000 |
| D12 | Earley trace recorded server-side, replayed client-side | Step back/forward is exact; the UI cannot show states the parser was never in |
| D13 | Derivation links per item (packed forest), not Earley's original tree recovery | The original procedure can yield spurious trees; links give exact counts and enumeration |
| D14 | Cyclic grammars rejected | A ⇒⁺ A gives infinitely many trees; counting/enumeration must terminate |
| D15 | Exercise answer keys: treebank gold or all grammar parses, never parser output | Parser output is not authoritative; all parses avoid rejecting valid alternatives |
| D16 | Span-based tree builder (bracketing) instead of free-form node dragging | Works with keyboard, touch and screen readers; nesting is always well-formed, so feedback can focus on linguistics |
