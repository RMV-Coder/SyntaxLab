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

The evidence is in [research/filipino-language-support.md](research/filipino-language-support.md)
and [research/nlp-model-evaluation.md](research/nlp-model-evaluation.md) §3.8.

- **No phrase-structure trees.** No parser or treebank for them exists, and SyntaxLab does not
  derive trees from dependencies.
- **Standard written Filipino/Tagalog only.** The model was trained on Manila news prose. Nothing
  is claimed for Taglish or other code-switching, social-media text, older literary Tagalog, or
  regional varieties. Mixed text is not detected: it is analyzed anyway, and the result is
  unreliable.
- **UD labels have Tagalog-specific meanings.** `nsubj` is the *ang*-phrase, whichever role it has
  in the event, so it is the patient of a patient-voice verb. Patient voice is annotated `Pass`,
  and calling it a passive is contested. Teaching notes say this, and are marked as drafts until a
  Filipino-language specialist has reviewed them.
- **The treebanks disagree with each other.** The model follows UD_Tagalog-NewsCrawl (*ang* is
  `det`). UD_Tagalog-TRG, a set of grammar-book examples, has *ang* as `case`, and differs on other
  points too. A label can therefore differ from another reference without being an error.
- **Known errors, shown as they are.** Capitalized first words can get an unreliable lemma and
  aspect (*Kumakain* as `Aspect=Perf`, *Bili* as a lemma). Adjectival predicates can be tagged
  VERB (*Maganda ang babae*). Lowercasing the first letter was measured and rejected, because it
  lowers parsing scores.
- **Attachment is much less reliable on long sentences.** Heads are right for about 94% of words in
  short grammar-book sentences and about 73% in news prose.
- **The linker is not split.** *magandang* stays one word, although the treebank analyzes it as
  *maganda* + *-ng*.
- **Sentence boundaries come from punctuation.** Common titles and initials are recognized. Another
  abbreviation can be mistaken for the end of a sentence, and then the API reports two sentences.
