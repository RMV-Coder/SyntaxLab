import { beforeEach, describe, expect, it } from "vitest";

import type { CheckResponse, ConstituencyFeedback } from "@/lib/api/types";
import correct from "@/e2e/fixtures/learn-check-tree-correct.json";
import partial from "@/e2e/fixtures/learn-check-tree-partial.json";

import { constituentMessage, problemMessage, treeSummary } from "./feedback-text";
import { readProgress, recordProgress } from "./progress";

const words = ["the", "student", "reads", "a", "book"];
const fb = (r: unknown) => (r as CheckResponse).feedback as ConstituencyFeedback;

describe("tree feedback wording", () => {
  it("confirms a correct tree and says how many trees the grammar allows", () => {
    const s = treeSummary(fb(correct));
    expect(s.solved).toBe(true);
    expect(s.body).toBe(
      "Your tree is the tree the grammar assigns. The grammar allows exactly one tree for this sentence.",
    );
  });

  it("explains partial answers relative to the closest parse", () => {
    const f = fb(partial);
    const s = treeSummary(f);
    expect(s.solved).toBe(false);
    expect(s.body).toMatch(/% of your constituents are in that parse/);
    const missing = f.constituents.filter((c) => c.status === "missing");
    expect(missing.map((c) => constituentMessage(c, words))).toEqual([
      "Missing: NP over “a book”.",
    ]);
    expect(f.problems.map(problemMessage)).toEqual([
      "The grammar has no rule VP → V Det N (for “reads a book”).",
    ]);
  });

  it("distinguishes other readings from unlicensed constituents", () => {
    const base = { label: "NP", start: 3, end: 5 };
    expect(constituentMessage({ ...base, status: "other_reading" }, words)).toMatch(/different reading/);
    expect(constituentMessage({ ...base, status: "unlicensed" }, words)).toMatch(/does not allow it/);
  });
});

describe("progress", () => {
  beforeEach(() => window.localStorage.clear());

  it("keeps the best score and remembers solved exercises", () => {
    recordProgress("a", 0.5, false);
    recordProgress("a", 1, true);
    recordProgress("a", 0.2, false);
    expect(readProgress()).toEqual({ a: { solved: true, best: 1 } });
  });

  it("survives corrupt storage", () => {
    window.localStorage.setItem("syntaxlab.learn.progress.v1", "{not json");
    expect(readProgress()).toEqual({});
  });
});
