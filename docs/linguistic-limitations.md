# Linguistic Limitations

What SyntaxLab's analyses can and cannot tell you. The research behind this page is in
[research/linguistic-limitations.md](research/linguistic-limitations.md).

## All languages

- **One analysis per sentence.** The parsers return their single best analysis. Ambiguous
  sentences such as *I saw the man with a telescope* have several valid structures, but you
  will see only one, and the parser does not indicate that others exist.
- **Analyses can be wrong.** Accuracy figures measure agreement with expert annotation on
  specific corpora. Unusual sentences, informal text, typos, and very long sentences are
  harder.
- **No confidence scores.** The models do not provide calibrated confidence, so SyntaxLab does
  not invent any.
- **Explanations describe labels, not the model's reasoning.** A definition tells you what
  `nsubj` means in the annotation scheme. It cannot tell you why the model chose it.

## English

- **Two models, two traditions.** The dependency graph follows Universal Dependencies v2; the
  phrase-structure tree follows the Penn Treebank. They come from separate models and can
  disagree. For example, in *I don't like the man with a telescope* the dependency model
  attaches *telescope* to *like* while the constituency model attaches the PP to *the man*.
  Neither view is derived from the other.
- **Penn Treebank labels are not textbook labels.** The trees use `NN`, `VBD`, `DT`, `SBAR` and
  flat noun phrases, without X-bar levels. The explanations give the closest textbook category
  (N, V, Det, CP, …) as a reading aid, but the correspondence is approximate. Trees are shown
  exactly as the parser produced them, never relabelled.
- **Auxiliaries nest verb phrases.** In Penn Treebank style, *is eating rice* is a VP
  containing another VP. That is the treebank's convention, not an error.
- **Measured accuracy** (dependency, UD English-EWT test, gold tokenization): LAS 89.7 overall.
  Passives are the weakest category in our regression set (LAS 86.3).
- **Performance.** Parsing runs on CPU and takes about 1–5 seconds per sentence. Text is
  limited to one sentence, 300 characters, and 40 words.

## Filipino (Tagalog)

Not yet enabled. Evaluated limitations are documented in
[research/filipino-language-support.md](research/filipino-language-support.md):

- There is no constituency parser.
- UD labels such as `nsubj` carry a Tagalog-specific meaning (the *ang*-phrase).
- There are known errors on capitalized verbs and adjectival predicates.
