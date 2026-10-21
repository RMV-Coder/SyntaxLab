# Parsing Algorithms: the Earley Parser in the Algorithm Lab

The Algorithm Lab runs an Earley parser, implemented from scratch for SyntaxLab, on small,
explicit context-free grammars and lets you replay every step it took. Why Earley and not CYK
is discussed in [research/parsing-strategies.md](research/parsing-strategies.md).

> **Scope:** the bundled grammars are teaching fragments. They do not describe English (or any
> language) as a whole, and the Lab does not claim to parse unrestricted text. The Analyzer's
> statistical parsers are a separate component.

## Grammar notation

```text
# comments start with #
S    -> NP VP
NP   -> Det N | NP PP | "I"        # alternatives with |
N'   -> Adj N'                      # primes allowed in names (X-bar style)
Det  -> "the" | 'a' | ε             # words in quotes; ε (or "") for the empty string
     | "this"                       # a line starting with | continues the previous rule
```

- The first rule's left-hand side is the start symbol. The parser adds the augmented rule
  `γ → S` (rule 0).
- Words are single tokens without spaces. Sentences are split on spaces, and punctuation marks
  become separate tokens. Words match case-insensitively.
- Any context-free rule is allowed: rules can mix words and categories (`VP → "to" V`), use ε,
  or be left- or right-recursive.

### Validation

`POST /api/v1/grammar/validate` reports problems with line numbers.

| Severity | Code | Meaning |
|---|---|---|
| error | `missing_arrow`, `bad_lhs`, `bad_symbol`, `epsilon_not_alone`, `empty_terminal`, `empty_alternative`, `dangling_alternative`, `no_rules` | Syntax |
| error | `undefined_symbol` | A category is used but never defined (or a word is missing its quotes) |
| error | `cyclic_grammar` | A ⇒⁺ A through unit rules and empty context: infinitely many trees for some sentences |
| error | `start_unproductive` | The start symbol cannot derive any sentence |
| error | `too_many_rules`, `rule_too_long`, `symbol_too_long` | Limits: 200 rules, 12 symbols per right-hand side, 32 characters per symbol |
| warning | `unproductive_symbol`, `unreachable_symbol`, `duplicate_rule` | Rules that can never take part in a parse |

Left recursion (`NP → NP PP`) is **not** a cycle and is fully supported.

## The algorithm

Items are dotted rules with an origin, `A → α • β [i]`. `chart[k]` holds the items ending at
position *k* (between words *k* and *k+1*), in the order they were added. Starting from
`γ → • S [0]`, each item in each set is processed exactly once:

| Operation | When | Effect |
|---|---|---|
| **Predict** | the next symbol is a category B | add `B → • γ [k]` for every rule of B |
| **Skip empty** (Aycock & Horspool) | B is *nullable* | also add `A → α B • β [i]` at once |
| **Scan** | the next symbol is a word that matches word *k+1* | add the advanced item to `chart[k+1]` |
| **Dead end** | the next word does not match, or the sentence has ended | recorded, nothing added |
| **Complete** | the item is finished and spans *i..k* with *i < k* | advance every item in `chart[i]` waiting for its category |

The sentence is accepted iff `γ → S • [0]` is in `chart[n]`.

**Empty rules** are the classic difficulty of Earley parsing. A completion over an empty span
can come too late for items added afterwards. SyntaxLab follows Aycock & Horspool (2002): the
predictor moves past nullable categories immediately. All empty-span derivations are carried
by these "skip empty" links, so the completer ignores empty-span completions and no
derivation is counted twice.

### Parse trees: a shared packed forest

Every advanced item keeps its **derivation links**: *(previous item, child)*, where the child
is a scanned word, a completed item, or an empty derivation of a nullable category. Together
the links form a shared packed parse forest (cf. Scott, 2008). From it:

- the **exact number of trees** is computed by dynamic programming. The number may be huge:
  ten `+` operators in the ambiguous arithmetic grammar give 16,796. It is reported exactly up
  to 10¹².
- **Trees are enumerated lazily**, at most 50 per request (20 by default).

This avoids a known pitfall: Earley's original tree-recovery procedure can produce trees the
grammar does not license.

### Complexity and limits

O(n³) in the worst case, O(n²) for unambiguous grammars. Lab limits: 20 words, 200 rules,
12,000 characters of grammar. The execution trace is capped at 20,000 events. A truncated
trace is flagged, and the outcome is still complete.

## The execution trace and replay

The server records each operation as it happens: `init`, `predict`, `nullable`, `scan`,
`scan_fail`, `complete`, `accept`/`reject`. Each event names:

- the item added (or found to be already present),
- the item that caused it,
- for completions, the finished constituent, and
- for scans, the word position.

The browser **replays** that record. The chart at step *i* is exactly the items whose `step`
is ≤ *i*, so stepping backward is as exact as stepping forward. The UI cannot show a state the
parser was never in. Plain-language explanations are generated from the events
(`apps/web/features/lab/replay.ts`). Selecting a node in a finished tree jumps to the step
where that constituent was completed.

## How correctness is checked

`services/parser-api/tests/unit/test_earley.py`:

- **Independent oracle.** A brute-force, span-based enumeration of all derivations, written
  separately from the parser. On every tested sentence the two must produce *exactly* the same
  set of trees, with no duplicates. Tested sentences:
  - random sentences generated from each preset grammar, plus mutated (mostly ungrammatical)
    copies; each sample must contain both outcomes;
  - every string of up to 4 words over the vocabulary of four grammars built around empty
    rules, including Aycock & Horspool's own example and hidden left recursion.
- **Known results.** Ambiguity grows as the Catalan numbers: 1, 2, 5, 14, 42, 132 trees for
  1–6 operators, and 2, 5, 14, 42 for 1–4 stacked PPs. Two words in four nullable slots give
  C(4,2) = 6 trees.
- **Trace integrity.** Replaying the recorded events rebuilds the final chart exactly. Every
  scan matches its word, every completion pairs a finished item with an item waiting for its
  category, and every prediction expands the expected category.
- **Preset claims.** Each example sentence in `data/grammars/*.yaml` declares its expected
  outcome (accepted or rejected, number of trees), and the test-suite verifies it.

## Bundled grammars

| Preset | Demonstrates |
|---|---|
| Prepositional-phrase attachment | Left recursion; PP attachment ambiguity; Catalan growth |
| Coordination and modifier scope | *old men and women*; binary coordination ambiguity |
| Optional elements (empty rules) | ε-rules and the nullable shortcut |
| Ambiguous arithmetic | Operator-precedence ambiguity, for comparison with programming languages |

Presets are data files. Add one by dropping a YAML file in
`services/parser-api/data/grammars/`. It must compile, and its examples' expected outcomes
must hold, or the tests fail.

## References

- Earley, J. (1970). An efficient context-free parsing algorithm. *CACM* 13(2).
- Aycock, J., & Horspool, R. N. (2002). Practical Earley Parsing. *The Computer Journal* 45(6).
- Scott, E. (2008). SPPF-Style Parsing From Earley Recognisers. *ENTCS* 203(2).
- Jurafsky, D., & Martin, J. H. *Speech and Language Processing* (3rd ed. draft), chapters on
  context-free grammars and parsing.
