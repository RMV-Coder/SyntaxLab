# NLP Model Evaluation

Status: Phase 0 research. Last updated 2026-10-21.
Legend: **[Verified]** checked directly · **[Measured]** run by us, conditions stated ·
**[Literature]** from cited source · **[Assumption]** unconfirmed.

## 1. Test conditions for all measurements

| | |
|---|---|
| Machine | Windows 11 laptop, 6 physical / 8 logical cores, 1.2 GHz base clock, CPU only |
| Python | 3.12.13 (uv-managed venv); some checks also on 3.14.3 |
| Libraries | torch 2.14.1+cpu, stanza 1.15.0, spacy 3.8.16, calamancy model wheels v0.2.0 |
| Setting | **Gold tokenization**: treebank syntactic words are fed pre-tokenized. Scores therefore measure tagging and parsing *given correct tokens*, and are upper bounds for raw-text input |
| Metrics | Plain token-level accuracy over all words incl. punctuation. UAS = correct head. LAS = correct head + deprel (full label, subtypes included). UFeats = exact match of the full feature string |
| Scripts | `eval_tl.py`, `eval_en.py`, `latency_en.py` (to be committed under `services/parser-api/scripts/eval/` in Phase 2) |

These numbers come from our own runs. They are not comparable decimal-for-decimal with the
official CoNLL 2018 scorer, which aligns predicted tokenization and treats punctuation the same
way but differs in details. Treat differences under about 0.5 points as noise.

## 2. English

### 2.1 Candidates

| Library | Dependency | Constituency | Status |
|---|---|---|---|
| **Stanza 1.15.0** | UD v2 (`combined_charlm`: EWT + GUM + others) | PTB3-revised in-order transition parser (`ptb3-revised_charlm`) | Maintained. Apache-2.0 code **[Verified: PyPI, resources_1.15.0.json]** |
| spaCy `en_core_web_*` | ClearNLP-style labels (not UD) | none | Maintained. Labels incompatible with UD-based cross-lingual comparison **[Literature: spaCy docs]** |
| benepar 0.2.0 | n/a | PTB | **Last release Feb 2021**. Pins transformers 4.3-era. Rejected **[Verified: PyPI]** |

Stanza's published constituency F1 for the default English model is 93.16 (charlm) and
96.08 (electra-large), on the PTB test set, CoreNLP scorer **[Literature: Stanza constituency docs]**.
We did not re-evaluate constituency, because the PTB test set is LDC-licensed and not available
to us.

### 2.2 Measured: Stanza English dependency on UD_English-EWT test (2,077 sentences, 25,094 words)

| UPOS | Lemma | UFeats | UAS | LAS |
|---|---|---|---|---|
| 96.70 | 97.02 | 96.02 | 92.00 | 89.74 |

**Caveat:** the `combined` model is trained on EWT among other corpora, so this is an
**in-domain** test. Classroom sentences are short and usually easier, but stylistically different.

### 2.3 Measured: resources and latency (Stanza English)

- Disk: about 430 MB for the default `tokenize, mwt, pos, lemma, depparse, constituency`
  models, of which the pretrained word vectors (`pretrain`) are 102 MB, depparse 136 MB, and
  constituency 108 MB.
- Memory: peak working set **about 650 MB** with both pipelines loaded (Windows working set.
  Proper private-bytes measurement is listed under §4).
- Load: 6–40 s (the first load includes one-time initialization and disk cache warmup).
- Warm single-sentence latency, 12-word sentence, median of 5:

| Processors | 1 torch thread | 4 torch threads |
|---|---|---|
| tokenize, pos, lemma, depparse | 786 ms | 1,500 ms |
| tokenize, pos, constituency | 1,127 ms | 1,195 ms |
| full (dep + constituency) | 1,875 ms | 1,464 ms |

  With the default thread count (8), latencies were **2.9–5.7 s**, which indicates thread
  oversubscription. **[Decision]** Pin `torch.set_num_threads` to the host's vCPUs, and
  measure again on the deployment host in Phase 8.

### 2.4 Qualitative check (full pipeline output, verified by inspection)

All four probe sentences received linguistically standard analyses:

- *The child is eating rice.* → `nsubj(eating, child)`, `aux(eating, is)`, `obj(eating, rice)`.
  PTB: `(S (NP The child) (VP is (VP eating (NP rice))))`.
- *I saw the man with a telescope.* → PP attached to the **verb** in both views
  (`obl(saw, telescope)`, and `PP` under `VP`). That is one of two valid readings, and only
  one is returned.
- Yes/no question → `SQ`. Relative clause → `acl:relcl` / `SBAR (WHNP that)`. Coordinated
  clauses with an embedded passive → `nsubj:pass`, `aux:pass`, `advcl`, `conj`.

### 2.5 English decision

**[Decision]** Stanza 1.15 with `package="default"` (charlm, no transformer) for both
representations. The `default_accurate` (electra-large) packages would add about 1.3 GB of
transformer weights and raise CPU latency several-fold. That's not justified for an
educational tool on CPU hosting. This can be revisited if a GPU or larger host becomes
available.

## 3. Tagalog / Filipino

### 3.1 Resources found

| Resource | Size | License | Notes |
|---|---|---|---|
| UD_Tagalog-TRG | 128 sents / 734 tokens (UD site, current) | CC BY-SA 4.0 | Grammar-book examples. In official UD releases (tags r2.14–r2.18) **[Verified]** |
| UD_Tagalog-Ugnayan | 94 sents / 1,011 tokens | **CC BY-NC-SA 4.0** (non-commercial) **[Verified: README]**. Do not bundle into an MIT/Apache repo without a separate NC-licensed data directory | DepEd educational texts |
| **UD_Tagalog-NewsCrawl** | 15,619 sents (train 12,495 / dev 1,561 / test 1,563) | CC BY-SA 4.0 **[Verified: README]** | Leipzig Tagalog news 2011. Manual lemma, UPOS, feats, deprels. **Not in an official UD release** (no tags, `not-to-release` marker, dev branch only) **[Verified 2026-10-21]** |
| calamanCy v0.2.0 (`tl_calamancy_md/lg/trf`) | 214 MB / 482 MB / 1.7 GB wheels | MIT (HF model card tag) | spaCy pipelines trained on NewsCrawl + TRG + Ugnayan (+ TLUnified for NER). Released 2025-01-19 **[Verified: meta.json, README]** |
| Stanza | none | | No `tl`, `fil`, or `ceb` entry in `resources_1.15.0.json` (286 entries) **[Verified]** |
| Aquino et al. 2025 baselines | XLM-R large: UAS 86.9 / LAS 81.0 / UPOS 91.5 | | Paper results. No released checkpoint found in the HF `UD-Filipino` org via API **[Verified: API returned empty]** |

### 3.2 Train/test separation (verified)

calamanCy's v0.2.0 spaCy project (`models/v0.2.0/project.yml`) trains with
`--paths.train corpus/treebank/tl_newscrawl-ud-train.spacy` and `--paths.dev …-dev.spacy`. The
NewsCrawl **test** split is held out and used only by `evaluate-model` **[Verified]**. The
scores below are therefore not contaminated by training data.

### 3.3 Two evaluations of calamanCy v0.2.0 on UD_Tagalog-NewsCrawl test (1,563 sentences)

**(a) Official evaluation, published in the calamanCy repo** (`models/v0.2.0/evals/*/dep_newscrawl.json`,
`spacy evaluate`: raw-text input with the model's own tokenizer, aligned to gold. spaCy's
scorer **excludes punctuation** from UAS/LAS) **[Verified: files read]**:

| Model | UAS | LAS | UPOS (`pos_acc`) |
|---|---|---|---|
| md | 83.45 | 77.13 | 95.00 |
| lg | 82.90 | 76.50 | 94.99 |
| trf | 85.09 | 78.83 | 95.43 |

**(b) Our evaluation** (gold syntactic words fed pre-tokenized, including UD's split linker
`-ng`. Punctuation **included**. Full-label LAS) **[Measured]**:

| Model | UPOS | Lemma | UFeats | UAS | LAS |
|---|---|---|---|---|---|
| md | 90.86 | 86.28 | 94.92 | 77.17 | 68.86 |
| lg | 92.45 | 85.95 | 94.90 | 79.49 | 71.53 |
| trf | not completed: more than 20 CPU-minutes on this machine, stopped | | | | |

The two disagree by about 5 LAS and on the md/lg ordering. The likely causes are
punctuation scoring, and gold-tokenized input containing the split linker `-ng`, which the
model's own tokenizer never produces (see §3.5). **Neither number describes accuracy on short
classroom sentences**, which is the real use case. **[Decision]** Report both, with their
conditions, in the capability page. Choose between md and lg in Phase 4 using one consistent
scorer on raw text with SyntaxLab's tokenizer fix applied.

### 3.4 Measured: resources (calamanCy, Python 3.12, 4 torch threads)

| Model | Private memory after load | Load time | Warm latency, 15-word sentence | Wheel |
|---|---|---|---|---|
| md | 253 MB | 2.8 s | 19 ms | 214 MB |
| lg | 1,127 MB | 3.7 s | 17 ms | 482 MB |
| trf | 2,398 MB | 322 s (first load) | 335 ms | 1.7 GB |

Wheel SHA-256 (downloaded 2026-10-21 from `huggingface.co/ljvmiranda921/tl_calamancy_*/…-any-py3-none-any.whl`.
The upstream filename lacks a version and is rejected by uv, so it is renamed locally to
`tl_calamancy_<size>-0.2.0-py3-none-any.whl`):

```
md  ed8e18e09b7ac2664d97b05d0b66e638e4be20f2f2a96efea8a58693278d6b29
lg  c922c44f6bfadf01aa967dc15ae43ebd587750b717d4b6ad710162434791c220
trf 3f754a2e89fe4ef5691a5fa6e7d36f503593cb2c27610d34d61c22ff0959e21b
```

### 3.5 Measured: tokenization against gold surface tokens

Gold surface tokens are UD multiword tokens counted once, which is what a tokenizer should
output. Scored as bag-of-tokens P/R per sentence:

| Tokenizer | P | R | F1 | Sentences tokenized exactly |
|---|---|---|---|---|
| calamanCy default | 93.14 | 96.99 | **95.02** | 60.7% |
| default minus spaCy's letter–hyphen–letter infix rule | 97.21 | 98.25 | **97.72** | 79.5% |

Our default-tokenizer F1 (95.02) reproduces calamanCy's published `token_f` (95.01). That
validates the method. **Root cause:** spaCy's generic infix rule splits *nag-aral* into
`nag` `-` `aral`, whereas the treebank keeps hyphenated Tagalog words whole (274 hyphenated
affixed words such as *mag-asawa*, *pag-asa*, *pag-ibig* in dev+test alone). The model then
parses three fragments as three VERBs. **[Decision]** The Tagalog adapter removes that single
infix rule, as a documented, tested normalization. End-to-end parse accuracy with the fix is
still to be measured (Phase 4).

The linker *-ng* (*magandang* = *maganda* + *-ng*) is **not** split by the tokenizer. Gold
splits it (2,132 MWTs in test). The model was trained on spaCy-converted data and analyzes
*magandang* as one token (lemma output: "ganda na"). Displaying the linker as its own
grammatical element would need a post-hoc MWT layer. That is deferred, and documented as a
limitation for now.

### 3.6 Dependency-install finding (affects the Python version)

- `tl_calamancy_{md,lg,trf}` 0.2.0 declare `spacy-transformers==1.3.5`, which requires
  `transformers<4.37`. That resolves to `tokenizers 0.15.x`, whose wheels stop at cp313.
  On Python 3.14 the resolver can only succeed by falling back to `transformers 4.17.0`
  (2022), an untested combination **[Verified: uv dry-run]**.
- `tl_calamancy_lg` installed **with `--no-deps`** loads and parses correctly on **Python
  3.14.3 without spacy-transformers**. Its config references only core spaCy registries
  **[Verified]**. `md` has the same config structure **[Assumption: not separately
  load-tested on 3.14]**. `trf` genuinely needs spacy-transformers. In the 3.12 env that
  resolves to transformers 4.36.2 + tokenizers 0.15.2 **[Verified]**.

### 3.7 Tagalog decision

**[Decision]**

- `tl_calamancy_lg` is the provisional default, `md` is selectable through configuration, and
  the final choice comes after the Phase 4 evaluation.
- `trf` is excluded from the MVP: 2.4 GB private memory, 335 ms per sentence on CPU, an
  extremely slow first load, and it forces an obsolete `transformers` 4.36 stack.
- Model wheels are installed **`--no-deps`, pinned by SHA-256**, against SyntaxLab's own
  pinned spaCy. This avoids pulling the unused spacy-transformers/transformers 4.36 stack.
- Backend Python is **3.12**. It is verified for all three models, so trf stays a future option
  without a runtime change. 3.14 is verified for the lg path only.

## 4. Open measurement items (Phase 2/4)

- Memory of both adapters loaded together in one process, as private bytes. Windows
  working-set figures above are lower bounds.
- Latency on the actual deployment host (2 vCPU).
- End-to-end Tagalog accuracy on raw text with the hyphen fix, using one consistent scorer.
- Out-of-domain Filipino evaluation on short, textbook-style sentences. This requires a small
  gold set reviewed by a Tagalog linguist; it does not exist yet.

## References

- Qi, P., Zhang, Y., Zhang, Y., Bolton, J., & Manning, C. D. (2020). Stanza: A Python NLP Toolkit for Many Human Languages. *ACL System Demonstrations*.
- Miranda, L. J. V. (2023). calamanCy: A Tagalog Natural Language Processing Toolkit. *NLP-OSS 2023*. arXiv:2311.07171.
- Aquino, A., Miranda, L. J. V., & Or, E. M. T. (2025). The UD-NewsCrawl Treebank. arXiv:2505.20428.
- Stanza constituency models: https://stanfordnlp.github.io/stanza/constituency.html
- Stanza resources: https://github.com/stanfordnlp/stanza-resources (`resources_1.15.0.json`)
- calamanCy models: https://huggingface.co/ljvmiranda921/tl_calamancy_lg
- UD_English-EWT: https://github.com/UniversalDependencies/UD_English-EWT (CC BY-SA 4.0)
