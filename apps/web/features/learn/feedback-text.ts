/**
 * Wording for exercise feedback. Feedback states what it is relative to (one expert
 * annotation, or the parses of an explicit grammar) and does not present uncertain judgements
 * as definitive.
 */
import type {
  ConstituencyFeedback,
  ConstituentFeedback,
  StructureProblem,
} from "@/lib/api/types";

export function spanWords(words: string[], start: number, end: number): string {
  return words.slice(start, end).join(" ");
}

export function constituentText(c: { label: string; start: number; end: number }, words: string[]) {
  return `${c.label} over “${spanWords(words, c.start, c.end)}”`;
}

export function constituentMessage(c: ConstituentFeedback, words: string[]): string {
  const what = constituentText(c, words);
  switch (c.status) {
    case "correct":
      return `${what}: correct.`;
    case "missing":
      return `Missing: ${what}.`;
    case "other_reading":
      return `${what} belongs to a different reading of the sentence, which does not fit with the rest of your tree.`;
    case "unlicensed":
      return `No parse of this sentence has ${what}: the grammar does not allow it here.`;
  }
}

export function problemMessage(p: StructureProblem): string {
  switch (p.code) {
    case "no_rule":
      return `The grammar has no rule ${p.rule}${p.words ? ` (for “${p.words}”)` : ""}.`;
    case "unknown_category":
      return `${p.label} is not a category of this grammar.`;
    case "crossing":
      return `${p.label} over “${p.words}” crosses another constituent; constituents must nest.`;
    case "no_root":
      return `Add a category covering the whole sentence (“${p.words}”).`;
    case "several_roots":
      return "Join the pieces under one category covering the whole sentence.";
    case "uncovered_word":
      return `“${p.words}” is not inside any constituent.`;
    case "out_of_range":
      return `${p.label} covers words outside the sentence.`;
  }
}

export function treeSummary(f: ConstituencyFeedback): { title: string; body: string; solved: boolean } {
  const readings =
    f.parse_count === 1
      ? "The grammar allows exactly one tree for this sentence."
      : `The grammar allows ${f.parse_count} trees for this sentence, and each of them is accepted.`;
  if (f.status === "matches") {
    return {
      title: "Correct",
      solved: true,
      body:
        f.parse_count === 1
          ? `Your tree is the tree the grammar assigns. ${readings}`
          : `Your tree is parse ${f.matched_parse} of ${f.parse_count}. ${readings}`,
    };
  }
  const relative =
    f.parse_count > 1 ? ` Feedback is relative to the parse closest to yours (parse ${f.closest_parse}).` : "";
  return {
    title: f.status === "invalid" ? "Not a complete tree yet" : "Not quite",
    solved: false,
    body: `${Math.round(f.precision * 100)}% of your constituents are in that parse, and you have found ${Math.round(f.recall * 100)}% of its constituents.${relative}`,
  };
}
