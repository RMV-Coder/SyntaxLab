import { expect, test, type Page } from "@playwright/test";

import { mockLearnApi } from "./support";

const words = (page: Page) => page.getByRole("group", { name: "Words of the sentence" });

/** Bracket words first..last (word texts) with a category. */
async function bracket(page: Page, first: string, last: string, label: string, nth = 0) {
  await words(page).getByRole("button", { name: first, exact: true }).nth(nth).click();
  await words(page).getByRole("button", { name: last, exact: true }).nth(last === first ? nth : 0).click();
  await page.getByRole("combobox", { name: "Category", exact: true }).selectOption(label);
  await page.getByRole("button", { name: /^Add / }).click();
}

test("lists exercises by activity", async ({ page }) => {
  await mockLearnApi(page);
  await page.goto("/learn");
  for (const heading of ["Parts of speech", "Word relations", "Build a tree"]) {
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  }
  await expect(page.getByRole("link", { name: /There is no delivery\./ })).toBeVisible();
});

test("part-of-speech exercise compares answers with the annotation", async ({ page }) => {
  const posted: unknown[] = [];
  await mockLearnApi(page, posted);
  await page.goto("/learn/ud-en-pos-01");
  await expect(page.getByRole("heading", { name: "There is no delivery." })).toBeVisible();
  const selects = page.getByRole("combobox", { name: /^Part of speech of word/ });
  await expect(selects).toHaveCount(5);
  for (let i = 0; i < 5; i++) await selects.nth(i).selectOption("NOUN");
  await page.getByRole("button", { name: "Check my answer" }).click();
  await expect(page.getByText(/of 5 match the annotation/)).toBeVisible();
  await expect(page.getByText(/The annotation has/).first()).toBeVisible();
  await expect(page.locator("p", { hasText: "How answers are checked." })).toContainText("UD_English-EWT");
  expect(posted[0]).toMatchObject({ answer: { kind: "pos", tags: ["NOUN", "NOUN", "NOUN", "NOUN", "NOUN"] } });
});

test("dependency exercise builds a graph and shows the annotated one", async ({ page }) => {
  await mockLearnApi(page);
  await page.goto("/learn/ud-en-dependency-01");
  await expect(page.getByRole("heading", { name: "We hope you do!" })).toBeVisible();
  await page.getByRole("combobox", { name: "Head of “hope”" }).selectOption("0");
  await expect(page.getByRole("combobox", { name: "Relation of “hope”" })).toBeDisabled();
  await page.getByRole("combobox", { name: "Head of “We”" }).selectOption("2");
  await page.getByRole("combobox", { name: "Relation of “We”" }).selectOption("nsubj");
  await expect(page.getByRole("group", { name: "Your dependency graph" }).getByText("nsubj", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Check my answer" }).click();
  await expect(page.getByText("4 of 5 heads, 4 of 5 relations match the annotation")).toBeVisible();
  await page.getByRole("button", { name: "Show the annotated graph" }).click();
  await expect(page.getByRole("group", { name: "Annotated dependency graph" })).toBeVisible();
});

test("tree builder: a correct tree is accepted and progress is saved", async ({ page }) => {
  const posted: unknown[] = [];
  await mockLearnApi(page, posted);
  await page.goto("/learn/grammar-01");
  await bracket(page, "the", "book", "S");
  await bracket(page, "the", "student", "NP");
  await bracket(page, "the", "the", "Det");
  await bracket(page, "student", "student", "N");
  await bracket(page, "reads", "book", "VP");
  await bracket(page, "reads", "reads", "V");
  await bracket(page, "a", "book", "NP");
  await bracket(page, "a", "a", "Det");
  await bracket(page, "book", "book", "N");
  await expect(page.getByText("[S [NP [Det the] [N student]] [VP [V reads] [NP [Det a] [N book]]]]")).toBeVisible();

  await page.getByRole("button", { name: "Check my answer" }).click();
  await expect(page.getByText("Correct", { exact: true })).toBeVisible();
  await expect(page.getByText(/exactly one tree for this sentence/)).toBeVisible();
  await page.getByRole("button", { name: "Compare with the grammar's tree" }).click();
  await expect(page.getByRole("group", { name: "A correct tree" })).toBeVisible();

  await page.goto("/learn");
  await expect(page.getByText("1 of 4 solved")).toBeVisible();
});

test("tree builder: prevents crossing brackets and explains a partial tree", async ({ page }) => {
  await mockLearnApi(page);
  await page.goto("/learn/grammar-01");
  await bracket(page, "the", "student", "NP");
  await bracket(page, "student", "reads", "VP");
  await expect(page.getByRole("main").getByRole("alert")).toContainText("would cross NP over “the student”");
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByText("Your constituents (0)")).toBeVisible();

  for (const [a, b, l] of [["the", "book", "S"], ["the", "student", "NP"], ["the", "the", "Det"], ["student", "student", "N"], ["reads", "book", "VP"], ["reads", "reads", "V"], ["a", "a", "Det"], ["book", "book", "N"]]) {
    await bracket(page, a, b, l);
  }
  await page.getByRole("button", { name: "Check my answer" }).click();
  await expect(page.getByText("Not quite")).toBeVisible();
  await expect(page.getByText("Missing: NP over “a book”.")).toBeVisible();
  await expect(page.getByText("The grammar has no rule VP → V Det N (for “reads a book”).")).toBeVisible();
});

test("practice pages never scroll sideways", async ({ page }) => {
  await mockLearnApi(page);
  for (const path of ["/learn", "/learn/grammar-02", "/learn/ud-en-dependency-01"]) {
    await page.goto(path);
    await expect(page.locator("h1")).toBeVisible();
    const [scroll, width] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
    expect(scroll, path).toBeLessThanOrEqual(width);
  }
});
