import { describe, expect, it } from "vitest";

import { fixtures } from "@/lib/testing/fixtures";

import { highlightFor, pathToToken, spanText } from "./selection";

const sentence = fixtures.parseChild.sentences[0];
const label = (id: string) => sentence.constituency!.nodes.find((n) => n.id === id)!.label;

describe("selection highlights", () => {
  it("a word highlights itself, its arcs, and its path in the tree", () => {
    const eating = sentence.tokens.find((t) => t.form === "eating")!.id;
    const h = highlightFor(sentence, { kind: "token", id: eating });
    expect([...h.tokens]).toEqual([eating]);
    // every arc touching "eating" (it is the root: child, is, rice and "." depend on it)
    const touching = sentence.dependency!.arcs.filter(
      (a) => a.head === eating || a.dependent === eating,
    );
    expect(h.arcs.size).toBe(touching.length);
    expect(pathToToken(sentence, eating).map(label)).toEqual(["ROOT", "S", "VP", "VP", "VBG"]);
  });

  it("a phrase highlights exactly the words it spans", () => {
    const vp = sentence.constituency!.nodes.find((n) => n.label === "VP" && n.span[0] === 3)!;
    const h = highlightFor(sentence, { kind: "node", id: vp.id });
    expect([...h.tokens]).toEqual([3, 4, 5]);
    expect(spanText(sentence, 3, 5)).toBe("is eating rice");
  });

  it("an arc highlights its head and dependent", () => {
    const rice = sentence.tokens.find((t) => t.form === "rice")!.id;
    const h = highlightFor(sentence, { kind: "arc", dependent: rice });
    const arc = sentence.dependency!.arcs.find((a) => a.dependent === rice)!;
    expect(h.tokens).toEqual(new Set([rice, arc.head]));
  });

  it("nothing selected highlights nothing", () => {
    const h = highlightFor(sentence, null);
    expect(h.tokens.size + h.nodes.size + h.arcs.size).toBe(0);
  });
});
