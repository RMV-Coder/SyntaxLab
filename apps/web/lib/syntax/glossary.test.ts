import { describe, expect, it } from "vitest";

import { fixtures } from "@/lib/testing/fixtures";

import { glossFeatures, lookupLabel, posFamily } from "./glossary";

const udGlossary = fixtures.glossaries["ud-2"];
const featsGlossary = fixtures.glossaries["ud-feats"];
const uposGlossary = fixtures.glossaries["ud-upos"];

describe("lookupLabel", () => {
  it("finds exact entries", () => {
    const r = lookupLabel(udGlossary, "nsubj");
    expect(r.match).toBe("exact");
    expect(r.entry?.name).toBe("nominal subject");
  });

  it("falls back to the base relation for unknown subtypes and says so", () => {
    const r = lookupLabel(udGlossary, "obl:npmod");
    expect(r.match).toBe("base");
    expect(r.matchedLabel).toBe("obl");
  });

  it("reports missing labels and missing glossaries", () => {
    expect(lookupLabel(udGlossary, "nonsense").match).toBe("none");
    expect(lookupLabel(null, "nsubj").match).toBe("none");
  });
});

describe("glossFeatures", () => {
  it("produces Leipzig abbreviations in conventional order", () => {
    const parts = glossFeatures(
      { VerbForm: "Fin", Tense: "Pres", Number: "Sing", Person: "3", Mood: "Ind" },
      featsGlossary,
    );
    expect(parts.map((p) => p.gloss)).toEqual(["3", "SG", "PRS", "IND", "FIN"]);
    expect(parts.find((p) => p.gloss === "FIN")?.standard).toBe(false);
    expect(parts.find((p) => p.gloss === "SG")?.standard).toBe(true);
  });

  it("handles multi-valued features and skips values without a gloss", () => {
    const parts = glossFeatures({ PronType: "Int,Rel", Degree: "Pos" }, featsGlossary);
    expect(parts.map((p) => p.gloss)).toEqual(["INT", "REL"]);
  });

  it("returns nothing without a glossary", () => {
    expect(glossFeatures({ Number: "Sing" }, null)).toEqual([]);
  });
});

describe("posFamily", () => {
  it("reads the family from the POS glossary", () => {
    expect(posFamily(uposGlossary, "NOUN")).toBe("nominal");
    expect(posFamily(uposGlossary, "AUX")).toBe("verbal");
    expect(posFamily(uposGlossary, "UNKNOWN")).toBeNull();
  });
});
