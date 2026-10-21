# Roadmap

Each item ships only when it meets the Definition of Done: implemented, tested, documented,
limitations recorded, and no unsupported claims.

## Done

- **Analyzer (English):** dependency + constituency analysis, interactive diagrams,
  explanations, provenance, export, mobile layout.
- **Pluggable languages:** configuration-only language addition, engine plug-ins.
- **Practice (Learn):** POS and dependency exercises on UD gold annotations; tree building
  checked against every parse of an explicit grammar; graded, explained feedback.
- **Algorithm Lab:** Earley parser with a replayable trace, a packed parse forest, ε-rules,
  grammar validation, four preset grammars, and correctness checked against an independent
  oracle.

- **Production readiness:** Docker image with baked-in models, deployment guide (Hugging
  Face Space, Vercel, alternatives), security headers, WCAG 2.2 AA audit in E2E, error
  boundaries.

## Next

1. **Go live.** Create the repository, Space and Vercel project ([deployment.md](deployment.md)).
   Run the image job in CI, and measure cold start, latency and memory on the host.

## Later

- **Filipino (Tagalog):** dependency, POS and morphology via calamanCy v0.2.0. Evaluated in
  [research/filipino-language-support.md](research/filipino-language-support.md). It needs the
  tokenizer fix, an engine plug-in for spaCy, a capitalization experiment, and review of the
  teaching notes by a Filipino-language specialist.
- **Compare:** side-by-side analyses of two sentences in different languages. Observations are
  limited to what the analyses actually show (word order, markers, features), with no claims of
  equivalence between labels.
- **CYK** as a second algorithm, with an explicit Chomsky-normal-form conversion view.
- Further languages through configuration (Spanish, Japanese and others where evaluated models
  exist), each with its own evaluation and notes.

## Research questions

- Code-switching (e.g. Taglish): token-level language identification, mixed morphology
  (*nag-submit*), and evaluation data. This is not ordinary multilingual support, and is not
  planned for the MVP.
- Optional AI-written explanations, clearly labelled and never authoritative over parser output
  or curated definitions.
