import { describe, expect, it } from "vitest";

import { derivationBrackets, layoutDerivation } from "@/lib/syntax/derivation-layout";
import { fixtures } from "@/lib/testing/fixtures";

import {
  chartAtStep,
  completionStep,
  dottedRule,
  explainEvent,
  itemAt,
  stepSummary,
} from "./replay";

const telescope = fixtures.grammarTelescope;
const rejected = fixtures.grammarRejected;
const dogs = fixtures.grammarDogs;
const last = telescope.trace.length - 1;

describe("chartAtStep", () => {
  it("shows only the start item at step 0", () => {
    const chart = chartAtStep(telescope, 0);
    expect(chart[0].map((v) => dottedRule(v.rule, v.item.dot))).toEqual(["γ → • S"]);
    expect(chart.slice(1).every((column) => column.length === 0)).toBe(true);
  });

  it("grows monotonically and reaches the full chart at the last step", () => {
    let previous = 0;
    for (let step = 0; step <= last; step++) {
      const size = chartAtStep(telescope, step).flat().length;
      expect(size).toBeGreaterThanOrEqual(previous);
      previous = size;
    }
    expect(previous).toBe(telescope.chart.flat().length);
  });

  it("stepping back is exactly the earlier state", () => {
    const a = chartAtStep(telescope, 40).flat().map((v) => `${v.ref.set}:${v.ref.index}`);
    chartAtStep(telescope, 90);
    const b = chartAtStep(telescope, 40).flat().map((v) => `${v.ref.set}:${v.ref.index}`);
    expect(b).toEqual(a);
  });
});

describe("explainEvent", () => {
  const explain = (kind: string, response = telescope) => {
    const event = response.trace.find((e) => e.kind === kind)!;
    return explainEvent(response, event);
  };

  it("explains the start", () => {
    expect(explain("init").body).toMatch(/adds γ → • S at position 0/);
  });

  it("explains predictions with the rule and position", () => {
    const e = explain("predict");
    expect(e.title).toBe("Predict S");
    expect(e.body).toMatch(/γ → • S expects S at position 0, so the parser adds the rule S → • NP VP/);
  });

  it("explains scans with the matched word", () => {
    expect(explain("scan").body).toMatch(/expects the word “I”, and word 1 \(“I”\) matches/);
  });

  it("explains dead ends", () => {
    const e = explain("scan_fail");
    expect(e.tone).toBe("rejected");
    expect(e.body).toMatch(/expects “.+”, but word 1 \(“I”\) is different/);
  });

  it("explains completion with the span found", () => {
    const e = explain("complete");
    expect(e.title).toBe("Complete Pronoun");
    expect(e.body).toMatch(/Pronoun → “I” • has found a complete Pronoun covering word 1 \(“I”\)/);
  });

  it("explains acceptance with the number of trees", () => {
    expect(explain("accept").body).toMatch(/S covers the whole sentence\. There are 2 parse trees: the sentence is ambiguous/);
  });

  it("explains rejection and an incomplete sentence", () => {
    expect(explain("reject", rejected).body).toMatch(/does not generate it/);
    const end = rejected.trace.find((e) => e.kind === "scan_fail" && e.token == null)!;
    expect(explainEvent(rejected, end).body).toMatch(/the sentence has ended/);
  });

  it("explains skipping an empty constituent", () => {
    const e = explain("nullable", dogs);
    expect(e.body).toMatch(/can be empty \(ε\)/);
  });

  it("has an explanation for every recorded event", () => {
    for (const response of [telescope, rejected, dogs]) {
      for (const event of response.trace) {
        const e = explainEvent(response, event);
        expect(e.title.length).toBeGreaterThan(0);
        expect(e.body).not.toMatch(/undefined|null|NaN/);
      }
    }
  });
});

describe("trees and the chart", () => {
  it("links each tree node to the step where its constituent was completed", () => {
    const tree = telescope.trees[0];
    const step = completionStep(telescope, tree);
    expect(step).not.toBeNull();
    const event = telescope.trace[step!];
    const view = itemAt(telescope, event.item!);
    expect(view.rule.lhs).toBe("S");
    expect(view.complete).toBe(true);
    expect([view.item.origin, view.item.end]).toEqual([0, 7]);
  });

  it("the two readings differ in where the PP attaches", () => {
    const brackets = telescope.trees.map(derivationBrackets);
    expect(new Set(brackets).size).toBe(2);
    expect(brackets.some((b) => b.includes("[NP [NP [Det the] [N man]] [PP"))).toBe(true);
    expect(brackets.some((b) => b.includes("[VP [VP [V saw]"))).toBe(true);
  });

  it("counts progress", () => {
    const s = stepSummary(telescope, last);
    expect(s.items).toBe(telescope.chart.flat().length);
    expect(s.deadEnds).toBeGreaterThan(0);
  });
});

describe("layoutDerivation", () => {
  const measure = (text: string) => text.length * 8;

  it("puts words on one baseline in order and draws ε for empty constituents", () => {
    const layout = layoutDerivation(dogs.trees[0], measure);
    const leaves = layout.nodes
      .filter((n) => n.kind !== "nonterminal")
      .sort((a, b) => a.x - b.x);
    expect(leaves.map((n) => n.label)).toEqual(["ε", "ε", "dogs", "sleep"]);
    expect(new Set(leaves.map((n) => n.y))).toEqual(new Set([layout.wordY]));
    expect(derivationBrackets(dogs.trees[0])).toBe(
      "[S [NP [Det ε] [AdjP ε] [N dogs]] [VP [V sleep]]]",
    );
  });

  it("centres parents over their children", () => {
    const layout = layoutDerivation(telescope.trees[0], measure);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));
    for (const node of layout.nodes.filter((n) => n.kind === "nonterminal")) {
      const kids = layout.edges.filter((e) => e.from === node.id).map((e) => byId.get(e.to)!);
      expect(node.x).toBeCloseTo((kids[0].x + kids[kids.length - 1].x) / 2);
      expect(kids.every((k) => k.y > node.y)).toBe(true);
    }
  });
});
