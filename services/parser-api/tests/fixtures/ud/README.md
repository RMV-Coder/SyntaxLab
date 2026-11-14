# Universal Dependencies fixtures

`en_ewt_regression.conllu` is a subset of the **UD English Web Treebank (UD_English-EWT)**,
release r2.18, test split, selected by `scripts/build_en_regression.py`. Annotations are the
treebank's manual (gold) annotations, unchanged, plus one added comment line per sentence
(`# syntaxlab_categories = ...`) recording why the sentence was selected.

- Source: https://github.com/UniversalDependencies/UD_English-EWT (tag `r2.18`)
- License: **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
  https://creativecommons.org/licenses/by-sa/4.0/
- Citation: Silveira, N., Dozat, T., de Marneffe, M.-C., Bowman, S., Connor, M., Bauer, J.,
  & Manning, C. D. (2014). A Gold Standard Dependency Corpus for English. *LREC 2014*.

## Tagalog

Selected by `scripts/build_tl_regression.py`. Annotations are the treebanks' manual (gold)
annotations, unchanged.

`tl_trg_regression.conllu` is all of **UD_Tagalog-TRG**, release r2.18: grammar-book examples,
mostly from Schachter & Otanes (1972).

- Source: https://github.com/UniversalDependencies/UD_Tagalog-TRG (tag `r2.18`)
- License: CC BY-SA 4.0
- Authors: Stephanie Samson, Daniel Zeman, and Mary Ann C. Tan

`tl_newscrawl_regression.conllu` is a subset of **UD_Tagalog-NewsCrawl**, test split: every 8th
sentence of 5-25 words. NewsCrawl is on the UD `dev` branch and is not in an official UD release,
so it is cited by commit.

- Source: https://github.com/UniversalDependencies/UD_Tagalog-NewsCrawl (dev, commit `5b96142`)
- License: CC BY-SA 4.0
- Citation: Aquino, A., Miranda, L. J. V., & Or, E. M. T. (2025). The UD-NewsCrawl Treebank.
  arXiv:2505.20428.

This directory is distributed under CC BY-SA 4.0, separately from SyntaxLab's MIT-licensed code.
