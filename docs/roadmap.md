# Roadmap

Each item ships only when it meets the Definition of Done: implemented, tested, documented,
limitations recorded, and no unsupported claims.

## Done

- **Analyzer (English):** dependency + constituency analysis, interactive diagrams,
  explanations, provenance, export, mobile layout.
- **Pluggable languages:** configuration-only language addition, engine plug-ins.

## Next

1. **Algorithm Lab.** An Earley parser implemented from scratch on small, explicit grammars,
   with a step-by-step execution view: predict, scan, complete; pause, step back, reset. Includes
   ambiguity through a packed parse forest, ε-rules and cycle detection. Design in
   [research/parsing-strategies.md](research/parsing-strategies.md).
2. **Learn.** Part-of-speech and dependency exercises on expert-annotated UD sentences, and
   bracketing exercises checked against *every* parse an explicit grammar allows. No exercise
   uses parser output as its answer key.
3. **Deployment.** API Docker image on Hugging Face Spaces, web app on Vercel, latency and
   memory measured on the host.

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
