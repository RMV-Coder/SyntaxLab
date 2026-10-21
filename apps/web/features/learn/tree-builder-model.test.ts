import { describe, expect, it } from "vitest";

import { derivationBrackets } from "@/lib/syntax/derivation-layout";

import {
  addConstituent,
  chainOf,
  isComplete,
  moveInChain,
  nest,
  outline,
  PLACEHOLDER_ROOT,
  previewTree,
  relabel,
  removeConstituent,
  type Constituent,
} from "./tree-builder-model";

const words = ["I", "saw", "the", "man"];

function build(spans: [string, number, number][]): Constituent[] {
  let list: Constituent[] = [];
  spans.forEach(([label, s, e], i) => {
    const r = addConstituent(list, label, s, e, `id${i}`);
    if (!r.ok) throw new Error(`could not add ${label}`);
    list = r.list;
  });
  return list;
}

describe("adding constituents", () => {
  it("rejects brackets that would cross an existing one", () => {
    const list = build([["NP", 2, 4]]);
    const r = addConstituent(list, "VP", 1, 3);
    expect(r).toMatchObject({ ok: false, reason: "crossing", conflict: { label: "NP" } });
  });

  it("rejects exact duplicates but allows unary chains", () => {
    const list = build([["NP", 0, 1]]);
    expect(addConstituent(list, "NP", 0, 1)).toMatchObject({ ok: false, reason: "duplicate" });
    expect(addConstituent(list, "Pronoun", 0, 1).ok).toBe(true);
  });
});

describe("nesting and preview", () => {
  const full = build([
    ["S", 0, 4], ["NP", 0, 1], ["Pronoun", 0, 1], ["VP", 1, 4], ["V", 1, 2], ["NP", 2, 4],
    ["Det", 2, 3], ["N", 3, 4],
  ]);

  it("nests by containment regardless of the order of creation", () => {
    const reversed = build([
      ["N", 3, 4], ["Det", 2, 3], ["NP", 2, 4], ["V", 1, 2], ["VP", 1, 4], ["NP", 0, 1],
      ["Pronoun", 0, 1], ["S", 0, 4],
    ]);
    expect(derivationBrackets(previewTree(reversed, words))).toBe(
      derivationBrackets(previewTree(full, words)),
    );
  });

  it("builds the expected tree, with the first of a unary chain on top", () => {
    expect(derivationBrackets(previewTree(full, words))).toBe(
      "[S [NP [Pronoun I]] [VP [V saw] [NP [Det the] [N man]]]]",
    );
    expect(isComplete(full, words.length)).toBe(true);
  });

  it("uses a placeholder root until a constituent covers the whole sentence", () => {
    const partial = build([["NP", 2, 4], ["V", 1, 2]]);
    const tree = previewTree(partial, words);
    expect(tree.symbol).toBe(PLACEHOLDER_ROOT);
    expect(derivationBrackets(tree)).toBe(`[${PLACEHOLDER_ROOT} I [V saw] [NP the man]]`);
    expect(isComplete(partial, words.length)).toBe(false);
  });

  it("produces an indented outline", () => {
    expect(outline(full).map((n) => `${"  ".repeat(n.depth)}${n.constituent.label}`)).toEqual([
      "S", "  NP", "    Pronoun", "  VP", "    V", "    NP", "      Det", "      N",
    ]);
    expect(nest(full)).toHaveLength(1);
  });
});

describe("editing", () => {
  it("reorders a unary chain", () => {
    const list = build([["NP", 0, 1], ["Pronoun", 0, 1]]);
    const moved = moveInChain(list, "id1", "up");
    expect(chainOf(moved, "id1").map((c) => c.label)).toEqual(["Pronoun", "NP"]);
    expect(moveInChain(moved, "id1", "up")).toBe(moved); // already on top
  });

  it("relabels and removes", () => {
    const list = build([["NP", 0, 1]]);
    expect(relabel(list, "id0", "N")[0].label).toBe("N");
    expect(removeConstituent(list, "id0")).toEqual([]);
  });
});
