# Linguistic Limitations (research findings)

Status: Phase 0 research. Last updated 2026-10-21.
Legend: **[Verified]**, **[Measured]**, **[Literature]**, **[Assumption]**, **[Decision]** as defined in
`parsing-strategies.md`.

This document records what SyntaxLab's analyses **cannot** claim, and why. The user-facing
version will live in `docs/linguistic-limitations.md` once features exist. This file holds the
research basis for it.

---

## 1. Limitations common to all statistical parsers

1. **Parsers output one analysis.** Stanza and calamanCy return a single best tree; neither
   exposes k-best parses through its public API **[Verified: calamanCy uses spaCy's greedy
   `parser` factory (`TransitionBasedParser.v2`), not `beam_parser`. Stanza 1.15's
   constituency and depparse processors have no beam/k-best options]**. SyntaxLab will
   therefore *not* show alternative analyses for parser output. Alternatives come only from the
   Earley engine, where they are exact for the given grammar. **[Decision]**
2. **No calibrated confidence.** Neither pipeline exposes per-arc probabilities through its
   standard API. SyntaxLab will display no confidence scores for parser output. **[Decision]**
3. **Accuracy is corpus-relative.** Reported scores measure agreement with one treebank's
   annotation conventions on in-domain text. Agreement is not "correctness", and accuracy on
   out-of-domain text (classroom examples, poetry, chat) is typically lower. **[Literature]**
4. **Errors are presented as errors, not as alternatives.** When a parse is wrong, the UI must
   not rationalize it with a fluent explanation. Explanations describe what a *label means*
   (curated definitions), never why the model "chose" it. Model internals are not inspectable
   in that way. **[Decision]**

## 2. English

1. **Two annotation schemes.** Dependency output follows Universal Dependencies (UD v2,
   trained on EWT + other UD English corpora). Constituency output follows the **revised Penn
   Treebank** scheme (NML nodes, split hyphens). The two schemes are independent: an `nsubj`
   arc does not correspond one-to-one with an `NP` under `S`. **[Verified: Stanza resources]**
2. **PTB labels are not textbook labels.** The PTB has no `Det`, `N`, `V`, or `Adj` preterminals.
   It uses `DT`, `NN`/`NNS`/`NNP`, `VB*`, and `JJ`, and it has flat NPs (no N-bar), no X-bar
   levels, and `S` / `SBAR` / `SINV` / `SQ` clause types. Many introductory syntax courses teach
   X-bar or simplified trees (`S → NP VP`, `NP → Det N`). SyntaxLab must label PTB trees as
   PTB-style and must **not** relabel them to look like textbook trees. A relabelled tree
   would no longer be the parser's output. A static, documented PTB-to-textbook *glossary* is
   acceptable. **[Decision]**
3. **Constituency PP attachment.** The parser commits to one attachment in sentences such as
   *I saw the man with a telescope*. The UI must say that the sentence is ambiguous and that
   the parser shows one reading. The Algorithm Lab can show both. **[Decision]**

## 3. Tagalog / Filipino

### 3.1 Tagalog vs. Filipino

**[Literature / sociolinguistic fact]** *Filipino* is the national language of the Philippines
(1987 Constitution, Art. XIV §6). Its standard is historically based on Tagalog and is
codified by the Komisyon sa Wikang Filipino. In practice, written Manila-based Filipino and
Tagalog overlap heavily, but Filipino admits more borrowing (English, Spanish) and has its own
orthographic conventions.

All available treebanks are labelled **Tagalog** (ISO 639-1 `tl`). The largest (NewsCrawl) is
Manila news text from 2011, which is in effect standard written Filipino with code-mixing.
**[Verified: README]**

**[Decision]** The UI language label will be **"Filipino (Tagalog)"**, internal code `tl`, with
`fil` accepted as an alias. The capability page states that the model was trained on Tagalog
news text and is not validated on other registers (conversational, social-media, literary) or
on regional varieties.

### 3.2 Grammatical relations: the "subject" debate

**[Literature]** Tagalog marks one argument per clause with *ang* (or *si*, or an ang-form
pronoun). The verb's voice affix (*-um-*, *mag-*, *-in*, *-an*, *i-*) tells which semantic role
that argument has. The status of the ang-phrase is contested. It has been called subject,
topic, trigger, pivot, and absolutive (Schachter 1976; Kroeger 1993; Himmelmann 2005; Foley
2008). The "focus" terminology common in Philippine schools is itself a theoretical choice.

**[Verified: model label inventory]** calamanCy v0.2.0 and UD-NewsCrawl label the ang-phrase
`nsubj` and the non-ang agent `obj:agent` (34 dependency labels in total). This is **one
annotation convention** (UD-Tagalog as adapted by the NewsCrawl annotators), not a resolution
of the debate.

**[Decision]** For Tagalog:

- `nsubj` is explained as "the ang-marked argument (UD convention)", with a note that it does
  not behave like an English subject. The actor of a patient-voice clause is not `nsubj`.
- English and Tagalog `nsubj` arcs are **never** described as equivalent in the Compare view.
  Comparison observations are restricted to observable facts: word order, case-marker tokens,
  voice morphology present in `Voice=` features, and which semantic participant carries the
  ang-marker in each sentence.

### 3.3 Morphology

**[Verified: NewsCrawl paper]** NewsCrawl annotates `Voice` (Act, Pass, Bfoc, Lfoc, Cau) and
`Aspect` (Imp, Perf only, with no separate contemplative/prospective value). Reduplication and
infixation are reflected in lemmas and features, but there is **no morpheme segmentation**:
SyntaxLab cannot show *k-um-a-kain* as root + infix + reduplication from model output. A
rule-based morphological segmenter would be separate future work and would need its own
evaluation.

### 3.3a Measured model weaknesses on textbook-style input

See `filipino-language-support.md` §5. In short:

- Sentence-initial capitalized verbs get wrong lemmas and sometimes the wrong `Aspect`.
- Adjectival predicates (*Maganda ang bahay*) are tagged VERB.
- Some perfective/imperfective confusions.
- The generic tokenizer splits hyphenated words (fixed by the adapter, with measured effect).
- The linker *-ng* is never split, unlike in the gold standard.

These are shown as documented limitations, never silently corrected.

### 3.4 Constituency

**[Verified, to the extent searchable]** No publicly available Tagalog constituency treebank or
parser was found. Tagalog phrase structure is also theoretically contested (e.g. whether a VP
constituent exists; Kroeger 1993). **[Decision]** The Analyzer offers **no constituency view
for Filipino**. Any Tagalog toy grammar in the Algorithm Lab is labelled as one theoretical
model and requires review by a Tagalog linguist before release.

### 3.5 Code-switching

The NewsCrawl README states that the data contains Tagalog–English code-mixing, and a 2025
commit added a "code-switching analysis" to the annotations. The model has therefore seen
*some* code-mixed tokens. That does **not** amount to validated code-switching support.
Language-ID per token, mixed morphology (*nag-submit*), and evaluation are all absent.
**[Decision]** Code-switching remains out of MVP scope. Sentences with apparent English tokens
get a warning, not a claim of support.

## 4. Treebank provenance caveat

**[Verified 2026-10-21]** UD_Tagalog-NewsCrawl's README states "Data available since UD v2.15".
However, the GitHub repository has **no release tags**: compare UD_Tagalog-TRG, tagged r2.14
through r2.18. The data exists only on the `dev` branch, a `not-to-release` marker file is
present, and the UD treebank hub page returns 404. It is therefore publicly available
(CC BY-SA 4.0), but it should be described as "the UD_Tagalog-NewsCrawl treebank (UD GitHub,
dev branch)", **not** as part of an official UD release. Recheck this before publishing docs.

## References

- Foley, W. A. (2008). The place of Philippine languages in a typology of voice systems. In *Voice and Grammatical Relations in Austronesian Languages*. CSLI.
- Himmelmann, N. P. (2005). Tagalog. In A. Adelaar & N. P. Himmelmann (Eds.), *The Austronesian Languages of Asia and Madagascar*. Routledge.
- Kroeger, P. (1993). *Phrase Structure and Grammatical Relations in Tagalog*. CSLI.
- Schachter, P. (1976). The subject in Philippine languages: Topic, actor, actor-topic, or none of the above? In C. Li (Ed.), *Subject and Topic*. Academic Press.
- Schachter, P., & Otanes, F. T. (1972). *Tagalog Reference Grammar*. University of California Press.
- Aquino, A., Miranda, L. J. V., & Or, E. M. T. (2025). The UD-NewsCrawl Treebank: Reflections and Challenges from a Large-scale Tagalog Syntactic Annotation Project. arXiv:2505.20428.
- UD_Tagalog-NewsCrawl repository: https://github.com/UniversalDependencies/UD_Tagalog-NewsCrawl (dev branch)
