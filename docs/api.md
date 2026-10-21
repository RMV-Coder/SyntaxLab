# API Reference (v1)

Base URL in development: `http://127.0.0.1:8710`. The machine-readable contract is the
OpenAPI document at `/openapi.json` (interactive docs at `/docs`). The web client's TypeScript
types are generated from it (`pnpm api:types`), and CI fails if they are stale.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness: the process serves HTTP |
| GET | `/ready` | Readiness: configured models are loaded (503 until they are) |
| GET | `/api/v1/languages` | Languages this deployment supports, with status and capabilities |
| GET | `/api/v1/languages/{code}` | One language (code or alias): capabilities, schemes, limits, samples, notes |
| POST | `/api/v1/parse` | Analyze a sentence |
| GET | `/api/v1/schemes/{scheme_id}` | Curated explanations of the labels of an annotation scheme |
| GET | `/api/v1/grammar/presets` | Algorithm Lab: preset teaching grammars |
| GET | `/api/v1/grammar/presets/{id}` | A preset with its example sentences and their verified outcomes |
| POST | `/api/v1/grammar/validate` | Check a grammar; diagnostics with line numbers |
| POST | `/api/v1/grammar/parse` | Run the Earley parser: outcome, exact tree count, trees, chart and full trace |
| GET | `/api/v1/learning/exercises` | Practice exercises (parts of speech, word relations, tree building) |
| GET | `/api/v1/learning/exercises/{id}` | One exercise **without** its answer key, plus how answers are checked |
| POST | `/api/v1/learning/exercises/{id}/check` | Check an answer; feedback includes the answer key |

Endpoints for comparison will be added with that feature, and only then.

## POST /api/v1/learning/exercises/{id}/check

The answer's `kind` must match the exercise:

```jsonc
{ "answer": { "kind": "pos", "tags": ["DET", "NOUN", null] } }               // null = unanswered
{ "answer": { "kind": "dependency", "arcs": [{ "dependent": 1, "head": 2, "relation": "nsubj" }] } }
{ "answer": { "kind": "constituency",
              "constituents": [{ "label": "S", "start": 0, "end": 5 }] } }  // word spans, end exclusive
```

Answer keys:

- **pos / dependency**: the gold annotation from UD English-EWT, which the exercise detail
  names. Per-word status is `correct`, `incorrect`, `partial` or `unanswered`. `partial`
  means the right base relation where the annotation uses a subtype, e.g. `obl` vs
  `obl:unmarked`.
- **constituency**: **every** parse the Earley parser finds under the exercise's grammar, with
  ε-constituents removed.
  - `status` is `matches` (equals some parse; `matched_parse` says which), `partial`, or
    `invalid` (crossing brackets, no root, uncovered words).
  - Each constituent is `correct`, `missing`, `other_reading` (valid in another parse, but not
    together with the rest of the tree) or `unlicensed` (in no parse).
  - `problems` lists rule violations, e.g. `no_rule` with the rule the tree would need, such as
    `VP → V Det N`.
  - `reference` is the matched or closest parse.

Errors: **404 `unknown_exercise`**, and **422 `invalid_input`** (wrong kind, or wrong number of
entries).

## POST /api/v1/grammar/parse

```json
{ "grammar": "S -> NP VP
…", "sentence": "I saw the man with a telescope", "max_trees": 20 }
```

The response contains:

- `tokens` and `unknown_tokens` (positions of words no rule produces).
- `accepted`, plus `tree_count` (exact, capped at 10¹² with `tree_count_capped`).
- `trees`: up to `max_trees` derivation trees, each node with `symbol`, `kind`, `start`, `end`,
  `rule` and `children`.
- `chart`: per position, items as `{rule, dot, origin, end, step}`.
- `trace`: every recorded operation, with references to chart items as `{set, index}`.
- `grammar`: the normalized rules; rule 0 is `γ → start`.

Errors: **422 `invalid_grammar`** (with `details.diagnostics`), **422 `too_many_words`**
(> 20), **422 `empty_text`**, and **422 `invalid_request`** (grammar > 12,000 characters).
Details are in [parsing-algorithms.md](parsing-algorithms.md).

## POST /api/v1/parse

```json
{ "language": "en", "text": "I saw the man with a telescope.", "structures": ["dependency"] }
```

- `language`: code or alias.
- `structures` (optional): any of `dependency`, `constituency`. Omit it to get everything the
  language supports. Requesting an unsupported structure returns **422
  `unsupported_structure`**; it is never substituted.

Response (abridged):

```jsonc
{
  "language": { "code": "en", "name": "English" },
  "text": "I saw the man with a telescope.",          // after Unicode NFC normalization
  "sentences": [{
    "text": "I saw the man with a telescope.",
    "start_char": 0, "end_char": 31,
    "tokens": [                                         // 1-based syntactic words
      { "id": 1, "form": "I", "lemma": "I", "upos": "PRON", "xpos": "PRP",
        "feats": { "Case": "Nom", "Number": "Sing", "Person": "1", "PronType": "Prs" },
        "start_char": 0, "end_char": 1 }
    ],
    "multiword_tokens": [],                             // e.g. "don't" -> words 2-3
    "dependency": { "scheme": "ud-2", "arcs": [ { "dependent": 1, "head": 2, "relation": "nsubj" } ] },
    "constituency": {
      "scheme": "ptb-revised", "root": "n0",
      "nodes": [ { "id": "n0", "label": "ROOT", "children": ["n1"], "token_id": null, "span": [1, 8] } ]
    }
  }],
  "provenance": {
    "engine": "stanza", "engine_version": "1.15.0", "model": "stanza:en:default",
    "components": [ { "capability": "dependency", "scheme": "ud-2",
                      "component": "stanza/en/depparse/combined_charlm" } ],
    "processing_ms": 1641.0, "cached": false
  },
  "notices": []
}
```

Invariants, validated server-side before every response (`analysis/validate.py`):

- Token ids are `1..n` in order. Multiword-token ranges are valid and do not overlap.
- Dependency: every word has exactly one head in `0..n`, there is exactly one root, and there
  are no cycles.
- Constituency: one root, every other node has exactly one parent, there are no cycles, every
  node is reachable, pre-terminals (`token_id` set) have no children, the yield covers words
  `1..n` exactly once in order, and every `span` equals the recomputed span.

A violation returns **500 `invalid_engine_output`**. The structure is never repaired.

There is deliberately no confidence field.

## Errors

All errors share one shape:

```json
{ "error": { "code": "too_many_sentences", "message": "Found 2 sentences; analyze up to 1 at a time.",
             "details": { "sentences": 2, "max_sentences": 1 } } }
```

| HTTP | `code` | When |
|---|---|---|
| 404 | `unsupported_language` | Unknown language code/alias (`details.supported` lists codes) |
| 404 | `unknown_scheme` | No glossary for that scheme |
| 404 | `unknown_grammar` | No preset grammar with that id |
| 404 | `unknown_exercise` | No exercise with that id |
| 422 | `invalid_grammar` | The grammar has errors (`details.diagnostics`) |
| 413 | `payload_too_large` | Body over 16 KB |
| 422 | `invalid_request` | Malformed JSON or fields (submitted values are never echoed) |
| 422 | `empty_text`, `text_too_long`, `too_many_words`, `too_many_sentences`, `invalid_input` | Input limits; control or bidirectional-override characters |
| 422 | `unsupported_structure` | Structure not supported by the language |
| 429 | `rate_limited` | Per-client token bucket exhausted (`Retry-After`) |
| 500 | `engine_failure`, `invalid_engine_output`, `internal_error` | Back-end failure; messages never contain internals |
| 503 | `model_unavailable` | Models failed to load |
| 503 | `overloaded` | Analysis queue full (`Retry-After: 5`) |
| 504 | `analysis_timeout` | Analysis exceeded the timeout |

## Limits (defaults; per-language overrides in `languages.yaml`)

| Setting (`SYNTAXLAB_…`) | Default |
|---|---|
| `DEFAULT_MAX_CHARS` / `DEFAULT_MAX_WORDS` / `DEFAULT_MAX_SENTENCES` | 300 / 40 / 1 |
| `MAX_BODY_BYTES` | 16384 |
| `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_BURST` | 60 / 10 (0 disables) |
| `MAX_QUEUE` (pending analyses per language) | 8 |
| `ANALYSIS_TIMEOUT_S` | 30 |
| `CACHE_SIZE` (LRU entries per language) | 256 |
| `CPU_THREADS` (torch intra-op threads) | number of CPUs |
| `CORS_ORIGINS` | `["http://localhost:3000","http://127.0.0.1:3000"]` |
| `TRUST_PROXY_HEADERS` | false (enable only behind a trusted proxy) |
| `PRELOAD` | true (load models at startup) |
