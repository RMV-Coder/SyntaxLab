import { describe, expect, it } from "vitest";

import type { DependencyArc } from "@/lib/api/types";
import { fixtures } from "@/lib/testing/fixtures";

import {
  layoutConstituency,
  phraseNodeIds,
  toBracketNotation,
  type Measure,
} from "./constituency-layout";
import { arcLevels, layoutDependency } from "./dependency-layout";

/** Deterministic text measure: 8px per character. */
const measure: Measure = (text) => text.length * 8;

const childSentence = fixtures.parseChild.sentences[0];
const questionSentence = fixtures.parseQuestion.sentences[0];

describe("layoutConstituency", () => {
  const tree = childSentence.constituency!;
  const layout = layoutConstituency(tree, childSentence.tokens, new Set(), measure);

  it("places one pre-terminal per word, in sentence order, on a shared baseline", () => {
    const leaves = layout.nodes.filter((n) => n.kind === "preterminal");
    expect(leaves.map((n) => n.text)).toEqual(["The", "child", "is", "eating", "rice", "."]);
    expect(new Set(leaves.map((n) => n.y)).size).toBe(1);
    const xs = leaves.map((n) => n.x);
    expect(xs).toEqual([...xs].sort((a, b) => a - b));
  });

  it("puts every phrase above its children and centred over their span", () => {
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));
    for (const node of layout.nodes.filter((n) => n.kind === "phrase")) {
      const kids = layout.edges.filter((e) => e.from === node.id).map((e) => byId.get(e.to)!);
      expect(kids.every((k) => k.y > node.y)).toBe(true);
      expect(node.x).toBeCloseTo((kids[0].x + kids[kids.length - 1].x) / 2);
    }
  });

  it("keeps every node inside the computed canvas", () => {
    for (const n of layout.nodes) {
      expect(n.x).toBeGreaterThan(0);
      expect(n.x).toBeLessThan(layout.width);
      expect(n.y).toBeLessThan(layout.height);
    }
  });

  it("collapses a phrase into a leaf covering its words (triangle notation)", () => {
    const np = tree.nodes.find((n) => n.label === "NP" && n.span[0] === 1)!;
    const collapsed = layoutConstituency(tree, childSentence.tokens, new Set([np.id]), measure);
    const leaf = collapsed.nodes.find((n) => n.id === np.id)!;
    expect(leaf.kind).toBe("collapsed");
    expect(leaf.text).toBe("The child");
    expect(leaf.y).toBeLessThan(collapsed.leafY); // label stays at its level; triangle spans down
    expect(leaf.tokenIds).toEqual([1, 2]);
    expect(collapsed.nodes.some((n) => n.text === "The" && n.kind === "preterminal")).toBe(false);
  });

  it("renders labelled bracket notation faithfully", () => {
    expect(toBracketNotation(tree, childSentence.tokens)).toBe(
      "[ROOT [S [NP [DT The] [NN child]] [VP [VBZ is] [VP [VBG eating] [NP [NN rice]]]] [. .]]]",
    );
  });

  it("lists collapsible phrases (never the root)", () => {
    const ids = phraseNodeIds(tree);
    expect(ids).not.toContain(tree.root);
    expect(ids.length).toBe(tree.nodes.filter((n) => n.token_id == null).length - 1);
  });
});

describe("arcLevels", () => {
  const arc = (dependent: number, head: number, relation = "dep"): DependencyArc => ({
    dependent,
    head,
    relation,
  });

  it("nests arcs by span containment", () => {
    // 1 <- 2 <- 4, 3 <- 4 : the arc 2-4 contains 3-4.
    const levels = arcLevels([arc(1, 2), arc(2, 4), arc(3, 4), arc(4, 0)]);
    expect(levels.get(1)).toBe(1);
    expect(levels.get(3)).toBe(1);
    expect(levels.get(2)).toBe(2);
    expect(levels.has(4)).toBe(false); // root arc is drawn separately
  });

  it("does not raise an arc because another arc crosses it", () => {
    // 1-3 and 2-4 cross; only containment (3-4 inside 2-4) raises a level.
    const levels = arcLevels([arc(1, 3), arc(2, 4), arc(3, 0), arc(4, 3)]);
    expect(levels.get(4)).toBe(1);
    expect(levels.get(1)).toBe(1);
    expect(levels.get(2)).toBe(2);
  });
});

describe("layoutDependency", () => {
  const dep = questionSentence.dependency!;
  const layout = layoutDependency(questionSentence.tokens, dep.arcs, measure);

  it("draws every non-root arc from its head to its dependent", () => {
    expect(layout.arcs).toHaveLength(dep.arcs.length - 1);
    const x = new Map(layout.tokens.map((t) => [t.id, t.x]));
    const sentenceLength = questionSentence.tokens.length;
    for (const a of layout.arcs) {
      expect(a.x2).toBe(x.get(a.dependent));
      expect(Math.abs(a.x1 - x.get(a.head)!)).toBeGreaterThan(0);
      expect(Math.abs(a.x1 - x.get(a.head)!)).toBeLessThanOrEqual(4 * sentenceLength);
      expect(a.top).toBeLessThan(layout.baseY);
    }
  });

  it("staggers arcs that leave the same word on the same side", () => {
    const starts = new Map<string, number[]>();
    for (const a of layout.arcs) {
      const key = `${a.head}:${Math.sign(a.x2 - a.x1)}`;
      starts.set(key, [...(starts.get(key) ?? []), a.x1]);
    }
    for (const xs of starts.values()) expect(new Set(xs).size).toBe(xs.length);
  });

  it("marks exactly the parser's root", () => {
    const rootArc = dep.arcs.find((a) => a.head === 0)!;
    expect(layout.root?.tokenId).toBe(rootArc.dependent);
  });

  it("preserves the parser's relations without modification", () => {
    const original = new Map(dep.arcs.map((a) => [a.dependent, `${a.head}:${a.relation}`]));
    for (const a of layout.arcs) {
      expect(`${a.head}:${a.relation}`).toBe(original.get(a.dependent));
    }
  });
});
