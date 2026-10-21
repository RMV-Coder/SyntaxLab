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

This directory is distributed under CC BY-SA 4.0, separately from SyntaxLab's MIT-licensed code.
