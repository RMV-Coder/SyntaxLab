# Adding a Language

Adding a language to SyntaxLab is a **configuration change**. No API, schema, or frontend code
changes are needed. Clients discover languages, their capabilities, and their annotation
schemes from `GET /api/v1/languages`, and render only what each language declares.

This is enforced by tests:

- `services/parser-api/tests/api/test_extensibility.py` adds languages through YAML alone.
- The web client contains no language-specific code: run `grep -rn '"en"' apps/web/features`.

## Three pieces, all data

| Piece | Where | Purpose |
|---|---|---|
| Language entry | `services/parser-api/config/languages.yaml` | Engine, engine options, scheme per layer, samples, notes, limits |
| Engine | any installed Python package | Turns a back-end's output into SyntaxLab's schema |
| Glossary (only for a *new* scheme) | `services/parser-api/data/glossary/<scheme>.yaml` | Curated label explanations |

Glossaries are keyed by **annotation scheme**, not by language. A language whose engine
produces Universal Dependencies reuses `ud-2`, `ud-upos` and `ud-feats` automatically.
Language-specific caveats go in an entry's `language_notes`, e.g. what `nsubj` means for the
Tagalog *ang*-phrase.

## Case 1: Stanza already supports the language

The built-in `stanza` engine is generic. Example, Spanish with dependencies only:

```yaml
# services/parser-api/config/languages.yaml
languages:
  # ... existing entries ...
  - code: es
    name: Spanish
    native_name: Español
    engine: stanza
    engine_options:
      lang: es
      package: default
      processors: [tokenize, mwt, pos, lemma, depparse]   # capabilities follow this list
    schemes:
      pos: ud-upos
      morphology: ud-feats
      dependency: ud-2
    samples:
      - text: El niño come arroz.
    notes:
      - Describe evaluated accuracy and known limitations here.
```

Then:

```bash
cd services/parser-api
uv run syntaxlab-api download-models --language es
uv run syntaxlab-api check --language es --load
```

Startup validation rejects inconsistent entries. Every structure the engine produces must name
its scheme, and the config may not claim a scheme for a layer the engine does not produce.

## Case 2: a different NLP back-end

Write an engine class (see `src/syntaxlab_api/engines/base.py` for the contract) in **any
package**, and register it under the `syntaxlab.engines` entry-point group:

```toml
# pyproject.toml of your package
[project.entry-points."syntaxlab.engines"]
spacy = "syntaxlab_spacy.engine:SpacyEngine"
```

Install the package next to the API and reference the engine by name (`engine: spacy`), or
without packaging as `engine: "your.module:YourEngine"`.

The engine contract, which is checked by `analysis/validate.py` on every response:

- `capabilities()` reports exactly what the back-end produces. Never derive one structure from
  another (e.g. no constituency trees built from dependencies).
- `analyze()` returns the back-end's analysis faithfully: no relabelling, no re-attachment, no
  invented alternatives or confidence scores.
- Language-specific *normalization* (e.g. a tokenizer fix) belongs in the engine, must be
  documented and tested, and must be measured against gold data.
- Back-end failures raise `EngineError`. The API reports them; there is no fallback.

## Case 3: a new annotation scheme

If the language's analyses follow a scheme without a glossary (for example a different
constituency treebank), declare it under `schemes:` in `languages.yaml` and add
`data/glossary/<scheme-id>.yaml`:

```yaml
id: my-scheme
kind: constituency          # pos | features | dependency | constituency
source: https://link-to-the-annotation-guidelines
entries:
  NP:
    name: noun phrase
    definition: >-
      Written from the published guidelines, in plain language.
    textbook: NP            # optional reading aid
    language_notes:         # optional, per language code
      xx: Caveat specific to language xx.
```

The glossary is validated at startup. A missing glossary is allowed: the UI then states that
no curated definition exists. It never invents one.

## Before enabling a language for users

Follow `docs/research/` as the model:

1. Verify that the model exists and runs (`syntaxlab-api check --load`).
2. Evaluate it on held-out gold data and record the numbers and their conditions.
3. Write the measured accuracy and known failure patterns into the entry's `notes`.
4. Add gold-based regression tests (`tests/integration/`), never invented reference trees.
5. Have teaching notes for language-specific labels reviewed by a specialist.
