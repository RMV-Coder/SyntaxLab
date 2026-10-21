# Parsing Strategies

Status: Phase 0 research. Last updated 2026-10-21.

Legend used throughout SyntaxLab research docs:

- **[Verified]**: checked directly (source read, command run, or output inspected) during this research.
- **[Literature]**: established result from the cited publication; not re-derived here.
- **[Assumption]**: a working assumption that still needs confirmation.
- **[Decision]**: a choice made on the basis of the above.

This document covers two separate questions:

1. Which **statistical parsers** produce the dependency and constituency analyses shown in the
   Analyzer (see also `nlp-model-evaluation.md`).
2. Which **formal parsing algorithm** SyntaxLab implements from scratch for the Algorithm Lab.

---

## 1. Dependency vs. constituency are different representations

**[Literature]** A dependency analysis is a set of binary, labelled, directed head→dependent
relations between words (de Marneffe et al., 2021, Universal Dependencies). A constituency
(phrase-structure) analysis is a hierarchy of phrases over contiguous token spans (e.g. Penn
Treebank style, Marcus et al., 1993).

The two are not interconvertible in general:

- Constituency → dependency is possible with head rules (e.g. Collins 1999 head-finding rules),
  but the result depends on the head rules chosen.
- Dependency → constituency is underdetermined. A dependency tree does not say whether
  dependents of the same head form intermediate phrases (flat vs. binary-branching structure),
  it cannot represent phrase labels that aren't encoded in POS tags, and non-projective
  dependencies cannot be drawn as contiguous constituents at all.

**[Decision]** SyntaxLab never derives a constituency tree from a dependency tree (or the other
way round) and presents it as a parser analysis. Each representation is shown only when a
component that actually produces it is available for the language.

---

## 2. Statistical parsers for the Analyzer

Summary (details and measurements in `nlp-model-evaluation.md`):

| Need | Selected | Rejected alternatives and why |
|---|---|---|
| English dependency | Stanza `combined_charlm` depparse (UD) | spaCy `en_core_web_*`: dependency labels are ClearNLP-style, not UD, which hurts cross-lingual comparison with the UD-based Tagalog model |
| English constituency | Stanza `ptb3-revised_charlm` (in-order transition parser) | benepar: last release Feb 2021 (v0.2.0), pins transformers 4.3-era, unmaintained |
| Tagalog dependency | calamanCy `tl_calamancy_lg` v0.2.0 (spaCy, trained incl. UD-NewsCrawl) | Stanza: no Tagalog model in `resources_1.15.0.json` **[Verified]**; UDPipe: only small TRG/Ugnayan models were historically available |
| Tagalog constituency | **None exists.** Only the educational Earley grammar (Algorithm Lab) | No Tagalog constituency treebank is publicly available **[Assumption — none found]** |

Using one library (Stanza) for both English representations matters: both analyses come from
the **same tokenization**, so token IDs line up between the dependency view and the
constituency view of the same sentence.

---

## 3. Formal algorithm for the Algorithm Lab: Earley vs. CYK

### 3.1 CYK (Cocke–Younger–Kasami)

**[Literature]** Bottom-up dynamic programming over a triangular chart; O(n³·|G|) time.
Requires the grammar in **Chomsky Normal Form** (CNF): every rule is `A → B C` or `A → a`.

Strengths:

- The chart is a triangle, which makes a very legible visualization.
- Simple to implement and to verify.

Weaknesses for SyntaxLab:

- **CNF conversion changes the grammar the student wrote.** Ternary rules are binarized with
  invented nonterminals (`VP → V NP PP` becomes `VP → V X1`, `X1 → NP PP`). Unit rules
  (`NP → N`) are eliminated, and ε-rules are removed. The trees the algorithm builds are therefore
  trees of a *different grammar*. Showing the student's own tree requires reversing the
  transformation, so the visualized states stop matching what the student sees.
- Unit-rule elimination in particular erases levels of structure that linguistics courses
  care about (`NP → N`, `S → VP` in imperatives).

### 3.2 Earley

**[Literature]** Earley (1970). A chart parser that works on **any context-free grammar,
unchanged**. Each chart entry is a dotted item `A → α • β, i` (rule, progress, origin
position). There are three operations:

- **Predict**: the next symbol after the dot is a nonterminal B, so add `B → • γ` items.
- **Scan**: the next symbol is a terminal that matches the next word, so advance the dot.
- **Complete**: an item is finished, so advance every item waiting for its left-hand side.

Complexity is O(n³) worst case, O(n²) for unambiguous grammars, and linear for most LR(k)
grammars. Joop Leo's (1991) optimization makes right recursion linear as well.

Strengths for SyntaxLab:

- **No grammar transformation.** The visualized items are rules the student wrote, and the
  final tree uses exactly those rules.
- Every step has a natural, truthful explanation ("predicted NP because S → NP • VP needs an
  NP at position 0"). That maps directly onto the requirement to explain *which rule is
  evaluated and why a state is valid*.
- Handles left recursion (`NP → NP PP`) natively, which is needed for classic PP-attachment
  ambiguity examples.
- Rejected states have a precise meaning: a prediction that is never scanned or completed,
  so it is a dead end.

Known pitfalls to engineer around:

- **ε-rules.** The naive algorithm mishandles nullable nonterminals. Fix: precompute nullable
  symbols and advance past them during prediction (Aycock & Horspool, 2002, *Practical Earley
  Parsing*).
- **Tree recovery under ambiguity.** Earley's original tree-recovery procedure can produce
  spurious derivations (pointed out by Tomita, 1986). The correct approach builds a **shared
  packed parse forest (SPPF)** (Scott, 2008, *SPPF-Style Parsing From Earley Recognisers*) or
  keeps explicit per-item derivation links. Trees are then enumerated from the forest.
- **Infinite ambiguity.** Cyclic grammars (`A → A`, or `A → B`, `B → A`) produce infinitely
  many trees. The grammar validator must detect unit-rule cycles and reject or flag them, and
  tree enumeration must be capped.

### 3.3 Decision

**[Decision]** Implement **Earley** as the primary Algorithm Lab parser:

- Python implementation in the backend (`grammar` module), pure standard library, with no NLP
  dependency.
- The parser **emits a trace of real events** (predict/scan/complete, with the triggering item
  and rule) *as it runs*. The trace is returned to the frontend, which replays it, so step
  forward, step backward, pause, and reset are navigation over a recorded execution, not a
  simulation. No state is fabricated: if the algorithm didn't emit it, the UI can't show it.
- Ambiguity: derivation links (packed forest) plus tree enumeration with a configurable cap
  (default 20). The tree count is computed by dynamic programming over the forest, so the UI
  can say "showing 20 of 132 parses".
- Input bounds for the Lab: ≤ 20 tokens and ≤ 200 rules. These bound the trace size and keep
  the response small.

CYK may be added later as a second algorithm *with an explicit CNF-conversion view*. Shown as
its own step, the conversion becomes educational rather than hidden. It is not in the MVP.

### 3.4 Educational grammars

The bundled grammars are explicitly **toy fragments** written to demonstrate the algorithm:

- `english-basic`: S / NP / VP / PP / Det / N / V / P / Adj, including a PP-attachment
  ambiguity (`I saw the man with a telescope`).
- `english-recursive`: left-recursive NP/VP rules and coordination, used to show unbounded
  ambiguity growth (Catalan numbers).
- `tagalog-basic` (**stretch goal, requires linguistic review**): verb-initial clauses with
  ang/ng/sa-marked phrases. Tagalog phrase structure is theoretically contested. Kroeger (1993)
  argues against a VP constituent containing the object. Any Tagalog grammar must state its
  theoretical assumptions and must not be presented as *the* structure of Tagalog.

None of these grammars cover unrestricted English or Filipino, and the UI must say so.

---

## 4. Using the Earley grammar for Learning-mode constituency exercises

There is no redistributable gold English constituency treebank: the Penn Treebank is
LDC-licensed. That raises the question of what Learning-mode constituency exercises should be
checked against.

**[Decision]** Constituency exercises are defined **relative to an explicit educational
grammar**. The reference answer set is *every* parse the Earley parser finds for the exercise
sentence under that grammar. A student tree is accepted iff it is structurally identical to one
of them. This avoids rejecting a valid alternative (e.g. either PP attachment), with the scope
stated plainly in the UI: "correct relative to grammar X", not "correct English syntax".

Dependency exercises use **gold UD annotations** from CC BY-SA 4.0 treebanks (UD_English-EWT,
UD_Tagalog-NewsCrawl test split), with attribution. They never use parser output as the answer
key.

---

## References

- Aycock, J., & Horspool, R. N. (2002). Practical Earley Parsing. *The Computer Journal*, 45(6).
- Collins, M. (1999). *Head-Driven Statistical Models for Natural Language Parsing*. PhD thesis, UPenn.
- de Marneffe, M.-C., Manning, C. D., Nivre, J., & Zeman, D. (2021). Universal Dependencies. *Computational Linguistics*, 47(2).
- Earley, J. (1970). An efficient context-free parsing algorithm. *Communications of the ACM*, 13(2).
- Kroeger, P. (1993). *Phrase Structure and Grammatical Relations in Tagalog*. CSLI.
- Leo, J. (1991). A general context-free parsing algorithm running in linear time on every LR(k) grammar without using lookahead. *Theoretical Computer Science*, 82(1).
- Marcus, M., Santorini, B., & Marcinkiewicz, M. A. (1993). Building a large annotated corpus of English: the Penn Treebank. *Computational Linguistics*, 19(2).
- Scott, E. (2008). SPPF-Style Parsing From Earley Recognisers. *Electronic Notes in Theoretical Computer Science*, 203(2).
- Tomita, M. (1986). *Efficient Parsing for Natural Language*. Kluwer.
- Stanza constituency models: https://stanfordnlp.github.io/stanza/constituency.html
- benepar on PyPI: https://pypi.org/project/benepar/
