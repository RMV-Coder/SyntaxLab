# Filipino / Tagalog Language Support

Status: Phase 0 research. Last updated 2026-10-21.
Legend: **[Verified]** · **[Measured]** · **[Literature]** · **[Assumption]** · **[Decision]**
(see `parsing-strategies.md`). Measurement conditions are in `nlp-model-evaluation.md` §1.

## 1. Summary

- A usable Tagalog **dependency parser with POS, morphology, and lemmas** exists: calamanCy
  v0.2.0 (spaCy). It is trained on UD_Tagalog-NewsCrawl (12,495 training sentences) and scores
  **LAS 76.5–77.1 / UAS 82.9–83.5** on the held-out NewsCrawl test set (official evaluation).
- **No Tagalog constituency parser or constituency treebank** was found. SyntaxLab will not
  offer Filipino constituency analysis from a parser.
- The model has measurable, documentable weaknesses on exactly the short, textbook-style
  sentences students will type: capitalization sensitivity, aspect errors, adjectival
  predicates tagged as VERB, and hyphenated words split by the generic tokenizer (fixable).
- Recommended strategy: **D (hybrid)**. Use the pretrained parser, plus a thin, explicitly
  documented rule layer for tokenization only. **No rules that rewrite parser decisions.**

## 2. Resources

See `nlp-model-evaluation.md` §3.1 for the full table. In brief:

| Resource | Use in SyntaxLab | License |
|---|---|---|
| UD_Tagalog-NewsCrawl (15.6k sents, news, 2011) | Gold for evaluation and dependency exercises (test split) | CC BY-SA 4.0 |
| UD_Tagalog-TRG (128 sents, grammar-book examples) | Gold for **textbook-style** regression tests and exercises | CC BY-SA 4.0 |
| UD_Tagalog-Ugnayan (94 sents, DepEd texts) | Evaluation only, not bundled | CC BY-NC-SA 4.0 |
| calamanCy v0.2.0 md/lg/trf | Runtime analysis | MIT (model card) |

**Provenance caveat [Verified]:** NewsCrawl is on the UD GitHub `dev` branch only, with no
release tag and a `not-to-release` marker. Cite it as the GitHub dataset, not as "UD v2.x".

## 3. Tagalog vs. Filipino

All resources are labelled **Tagalog**. NewsCrawl is Manila news prose, i.e. standard written
Filipino with English code-mixing **[Verified: README]**. SyntaxLab labels the language
**"Filipino (Tagalog)"** (`tl`, alias `fil`). It claims validity only for **standard written
Filipino/Tagalog in a news-like register**. It makes no claims for conversational Taglish,
social-media text, older literary Tagalog, or regional varieties.

## 4. Annotation conventions the UI must explain

Verified from NewsCrawl test data (1,563 sentences) and the model's label inventory:

| Phenomenon | Annotation | Teaching note required |
|---|---|---|
| *ang* / *si* phrase | marker `DET Case=Nom`, phrase `nsubj` | "Subject" here is the UD label for the ang-marked argument. In patient voice it is the *patient*. Not equivalent to English subject |
| non-ang actor (*ng bata*, *ko*) | `obj:agent` (735 in test) | The actor of a non-actor-voice clause. UD-Tagalog-specific subtype |
| *ng* (genitive) | `ADP Case=Gen`, `case` | Same form marks non-ang patients (`obj`) and possessors (`nmod:poss`) |
| *sa* | `ADP Case=Loc`, `case` → `obl` | |
| Voice | `Voice=Act` 1,113 / `Pass` 1,448 / `Lfoc` 157 / `Cau` 78 / `Bfoc` 15 | Patient voice is annotated **`Pass`**. Calling it "passive" is a contested analysis (Tagalog patient voice is not a demoted-agent passive in the English sense). The UI must say so |
| Aspect | `Imp` 1,553 / `Perf` 1,261 only | Contemplative (*kakain*) has no distinct value |
| *ay* inversion | *ay* = `PART`/`discourse`, attached to the fronted phrase. The predicate remains root | *ay* is not analysed as a copula |
| Linker *-ng* / *na* | `PART`/`mark`, lemma *na*. *-ng* split as a multiword token (2,132 in test) | The model's tokenizer does **not** split *-ng* (§5) |
| Existential *may* | `VERB` (root 91×, …) | Matches gold. Explain as existential predicate |

## 5. Measured behaviour on targeted constructions

`tl_calamancy_lg` 0.2.0, raw text. ✓ = consistent with NewsCrawl conventions.

| Sentence | Result |
|---|---|
| *Kinakain ng bata ang kanin.* | ✓ `Voice=Pass`, *bata* `obj:agent`, *kanin* `nsubj` |
| *Ang bata ay kumakain ng kanin.* | ✓ *ay* `discourse`, *kumakain* root, `Aspect=Imp` |
| *Bumili ako ng libro sa tindahan.* | ✓ structure. Lemma *Bili* keeps the capital |
| *Binigyan ko ng regalo ang guro.* | ✓ `Voice=Lfoc`, *ko* `obj:agent`, *guro* `nsubj` |
| *May pusa sa bahay.* | ✓ per conventions (`may` VERB root) |
| *Kumakain ng kanin ang bata.* | Structure ✓. **✗ `Aspect=Perf`** and lemma *Kumakain*. The same word lowercased gets `Imp` and lemma *kain*. **Capitalization-sensitive** |
| *Hindi pa siya kumakain.* | Structure ✓. **✗ `Aspect=Perf`** |
| *Kumain ka na ba?* | Structure ✓. **✗ `Aspect=Imp`, `Mood=Pot`** |
| *Maganda ang bahay.* | **✗ *Maganda* tagged VERB** (gold has 271 ADJ roots in dev+test) |
| *Ang magandang babae ay guro.* | Structure ✓. *magandang* unsplit, VERB, lemma "ganda na" |
| *Nag-aral siya sa paaralan.* | **✗ default tokenizer splits *Nag* `-` *aral*** into three VERBs. **✓ after tokenizer fix** |
| *Nag-submit na ako ng requirements yesterday.* | Garbage by default. Plausible after the fix, but **code-switching remains unsupported** |

These probes are diagnostic examples, **not** gold standards. They were written for this
research and have not been reviewed by a Tagalog linguist. They must not become regression
fixtures until reviewed (see §8).

## 6. Strategy evaluation

| | A. Pretrained parser | B. Fine-tune multilingual model | C. Rule-based parser | D. Hybrid (A + thin rules) |
|---|---|---|---|---|
| Accuracy | LAS ~76–77 in-domain. Unknown on textbook sentences | Paper reports XLM-R large LAS 81.0, about +4, but **no released checkpoint found** | High on a tiny, curated fragment. Zero coverage outside it | A, plus tokenization fixes (+2.7 token F1 measured) |
| Complexity | Low | High: training infra, GPU, evaluation | Medium–high, and needs linguistic expertise | Low–medium |
| Dev time | Days | Weeks | Weeks | Days |
| Runtime cost | 0.25–1.1 GB RAM, ~20 ms/sentence | XLM-R large ~2+ GB, slow on CPU | Negligible | Same as A |
| Maintainability | Depends on upstream (calamanCy is 1-maintainer) | We own a model | We own a grammar | Small owned surface |
| Data | None | NewsCrawl train (available) | Grammar authoring | None |

**[Decision] D (hybrid), with strict limits on the rule layer:**

1. The rule layer may **only** change tokenization so that it matches the treebank the model was
   trained on (the hyphen fix). Every rule is unit-tested, and its effect is measured against
   gold.
2. Rules **never** override POS, features, heads, or labels. If the model says *Maganda* is a
   VERB, the UI shows VERB. Known systematic error patterns are documented on the capability
   page, and may be surfaced as **warnings**, e.g. "sentence-initial capitalised verbs may get
   unreliable aspect and lemma". They are never corrected silently.
3. Re-evaluate B only if A, measured on a reviewed textbook-style gold set, proves inadequate
   for the learning features. Option C stays limited to the Algorithm Lab, as a
   clearly-labelled toy grammar.

**Experiments queued for Phase 4** (each must be measured, not assumed):

- Lowercasing the sentence-initial token for analysis only, keeping the original form for
  display. This may fix the capitalization sensitivity. It is a modification of input, so it
  is only adopted if it improves the measured scores and is disclosed in provenance.
- A linker MWT layer that displays *magandang* as *maganda* + *-ng*. This is only possible if
  it can be done without altering parser output, and is likely deferred.
- md vs. lg on raw text with the fix, using one scorer.

## 7. Capabilities to expose (MVP)

| Capability | Filipino (Tagalog) | Basis |
|---|---|---|
| Tokenization | Yes, with documented hyphen normalization | Measured F1 97.7 vs gold surface tokens |
| UPOS | Yes | Official 95.0. Ours 92.5 (gold tokens) |
| Morphological features | Yes: Voice, Aspect, Mood, Case, Person, Number, … | UFeats exact 94.9 |
| Lemma | Yes, with capitalization caveat | 86–90 |
| Dependency (UD) | Yes | LAS 76.5 official |
| Constituency | **No** | No resource exists |
| Alternative analyses | **No** | Greedy parser, single output |
| Code-switching | **No** (warning only) | Not evaluated |

## 8. Needs human expertise (blocker for "validated Filipino test cases")

SyntaxLab cannot self-certify Tagalog linguistic correctness. Before Phase 4 is marked done:

- Regression fixtures come from **gold treebank sentences** (TRG for textbook style, NewsCrawl
  test for news). They are annotated by the treebank authors, not invented by us.
- Tagalog teaching notes in the glossary (§4 column 3) need review by a Tagalog linguist or
  Filipino-language educator. Until then they are marked "Draft, pending review" in the UI.

## References

- Aquino, A., Miranda, L. J. V., & Or, E. M. T. (2025). The UD-NewsCrawl Treebank. arXiv:2505.20428.
- Miranda, L. J. V. (2023). calamanCy: A Tagalog Natural Language Processing Toolkit. NLP-OSS 2023.
- calamanCy v0.2.0 training project: https://github.com/ljvmiranda921/calamanCy/tree/master/models/v0.2.0
- Kroeger, P. (1993). *Phrase Structure and Grammatical Relations in Tagalog*. CSLI.
- Schachter, P., & Otanes, F. T. (1972). *Tagalog Reference Grammar*. UC Press.
- Himmelmann, N. P. (2005). Tagalog. In *The Austronesian Languages of Asia and Madagascar*. Routledge.
