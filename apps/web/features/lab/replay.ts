/**
 * Replay of a recorded Earley execution.
 *
 * The parser runs once on the server and records every operation. Stepping forward, backward
 * or scrubbing is navigation over that record: the chart at step i is exactly the items whose
 * `step` is ≤ i. Nothing here simulates the algorithm.
 */
import type {
  ChartItem,
  DerivationTree,
  GrammarRule,
  ItemRef,
  ParseGrammarResponse,
  TraceEvent,
} from "@/lib/api/types";

export interface ItemView {
  ref: ItemRef;
  item: ChartItem;
  rule: GrammarRule;
  complete: boolean;
}

export function ruleOf(response: ParseGrammarResponse, index: number): GrammarRule {
  return response.grammar.rules[index];
}

export function itemAt(response: ParseGrammarResponse, ref: ItemRef): ItemView {
  const item = response.chart[ref.set][ref.index];
  const rule = ruleOf(response, item.rule);
  return { ref, item, rule, complete: item.dot === rule.rhs.length };
}

/** Dotted-rule text, e.g. `NP → Det • N`. Terminals are quoted as in the grammar notation. */
export function dottedRule(rule: GrammarRule, dot: number): string {
  const parts = rule.rhs.map((s) => (s.kind === "terminal" ? `“${s.value}”` : s.value));
  parts.splice(dot, 0, "•");
  return `${rule.lhs} → ${parts.join(" ")}`;
}

export function itemText(view: ItemView): string {
  return dottedRule(view.rule, view.item.dot);
}

/** Items visible at a step, per chart set, in insertion order. */
export function chartAtStep(response: ParseGrammarResponse, step: number): ItemView[][] {
  return response.chart.map((column, set) =>
    column.flatMap((item, index) =>
      item.step <= step ? [itemAt(response, { set, index })] : [],
    ),
  );
}

export function sameRef(a: ItemRef | null | undefined, b: ItemRef | null | undefined): boolean {
  return Boolean(a && b && a.set === b.set && a.index === b.index);
}

// ---------------------------------------------------------------------- explanations

export type EventTone = "progress" | "duplicate" | "rejected" | "accepted" | "start";

export interface Explanation {
  title: string;
  body: string;
  tone: EventTone;
}

const word = (response: ParseGrammarResponse, position: number) =>
  `word ${position + 1} (“${response.tokens[position]}”)`;

function span(response: ParseGrammarResponse, start: number, end: number): string {
  if (start === end) return "nothing (an empty span)";
  const words = response.tokens.slice(start, end).join(" ");
  return start + 1 === end ? `word ${start + 1} (“${words}”)` : `words ${start + 1}–${end} (“${words}”)`;
}

/** Plain-language explanation of one recorded event. */
export function explainEvent(response: ParseGrammarResponse, event: TraceEvent): Explanation {
  const added = event.item ? itemText(itemAt(response, event.item)) : "";
  const cause = event.cause ? itemText(itemAt(response, event.cause)) : "";
  const position = event.set;
  const start = response.grammar.start;

  switch (event.kind) {
    case "init":
      return {
        title: "Start",
        tone: "start",
        body: `The parser adds ${added} at position 0. The goal: find ${start} covering the whole sentence.`,
      };
    case "predict":
      return event.added
        ? {
            title: `Predict ${event.symbol}`,
            tone: "progress",
            body: `${cause} expects ${event.symbol} at position ${position}, so the parser adds the rule ${added}, starting at position ${position}.`,
          }
        : {
            title: `Predict ${event.symbol} (already there)`,
            tone: "duplicate",
            body: `${cause} also expects ${event.symbol}, but ${added} is already in set ${position}. Nothing new is added; each item is kept once.`,
          };
    case "nullable":
      return {
        title: `Skip empty ${event.symbol}`,
        tone: event.added ? "progress" : "duplicate",
        body: `${event.symbol} can be empty (ε), so ${cause} can also move past it without consuming a word: ${added}.${event.added ? "" : " That item is already in the chart."}`,
      };
    case "scan":
      return {
        title: `Scan “${event.symbol}”`,
        tone: "progress",
        body: `${cause} expects the word “${event.symbol}”, and ${word(response, event.token!)} matches. The dot moves past it: ${added}, now in set ${position}.`,
      };
    case "scan_fail":
      return {
        title: "Dead end",
        tone: "rejected",
        body:
          event.token == null
            ? `${cause} expects “${event.symbol}”, but the sentence has ended. This path cannot be completed.`
            : `${cause} expects “${event.symbol}”, but ${word(response, event.token)} is different. This path goes no further.`,
      };
    case "complete": {
      const done = event.completed ? itemAt(response, event.completed) : null;
      const found = done
        ? `${itemText(done)} has found a complete ${event.symbol} covering ${span(response, done.item.origin, done.item.end)}`
        : `A complete ${event.symbol} was found`;
      return {
        title: `Complete ${event.symbol}`,
        tone: event.added ? "progress" : "duplicate",
        body: `${found}. ${cause} was waiting for ${event.symbol}, so it moves forward: ${added}.${event.added ? "" : " That item is already in the chart (another way to reach the same state)."}`,
      };
    }
    case "accept": {
      const n = response.tokens.length;
      const trees =
        response.tree_count === 1
          ? "There is exactly one parse tree."
          : `There are ${response.tree_count_capped ? "more than " : ""}${response.tree_count.toLocaleString("en")} parse trees: the sentence is ambiguous under this grammar.`;
      return {
        title: "Accepted",
        tone: "accepted",
        body: `γ → ${start} • spans positions 0 to ${n}: ${start} covers the whole sentence. ${trees}`,
      };
    }
    case "reject": {
      const unknown = response.unknown_tokens.map((i) => `“${response.tokens[i]}”`);
      return {
        title: "Rejected",
        tone: "rejected",
        body:
          `No item γ → ${start} • covers the whole sentence, so the grammar does not generate it.` +
          (unknown.length ? ` No rule produces ${unknown.join(", ")}.` : ""),
      };
    }
  }
}

// ---------------------------------------------------------------------- trees ↔ chart

/** The step at which the chart item that built this tree node was completed. */
export function completionStep(response: ParseGrammarResponse, node: DerivationTree): number | null {
  if (node.kind !== "nonterminal" || node.rule == null) return null;
  const rule = ruleOf(response, node.rule);
  const item = response.chart[node.end]?.find(
    (i) => i.rule === node.rule && i.origin === node.start && i.dot === rule.rhs.length,
  );
  // Empty constituents are derived on the fly from nullable symbols and may have no item.
  return item ? item.step : null;
}

/** Summary counts for a step, e.g. for a progress line. */
export function stepSummary(response: ParseGrammarResponse, step: number) {
  const events = response.trace.slice(0, step + 1);
  return {
    items: events.filter((e) => e.added).length,
    deadEnds: events.filter((e) => e.kind === "scan_fail").length,
  };
}
