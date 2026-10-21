import { readFile } from "node:fs/promises";

import { expect, test, type Page } from "@playwright/test";

import { API, mockApi } from "./support";

const isMobile = (page: Page) => (page.viewportSize()?.width ?? 1280) < 1024;

async function openPanel(page: Page, name: "Sentence" | "Diagram" | "Details") {
  if (isMobile(page)) await page.getByRole("button", { name, exact: true }).click();
}

async function analyze(page: Page, sentence: string) {
  await openPanel(page, "Sentence");
  await page.getByRole("textbox", { name: "Sentence" }).fill(sentence);
  await page.getByRole("button", { name: "Analyze", exact: true }).click();
  await expect(page.getByTestId("diagram-canvas")).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("lists languages and examples discovered from the API", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("combobox", { name: "Language" })).toHaveText(/English/);
  await expect(page.getByText("I saw the man with a telescope.")).toBeVisible();
  await expect(page.getByText("Phrase structure", { exact: true })).toBeVisible();
  await expect(page.getByText("Word relations", { exact: true })).toBeVisible();
});

test("analyzes a sentence and draws the phrase-structure tree", async ({ page }) => {
  await page.goto("/");
  await analyze(page, "The child is eating rice.");
  const canvas = page.getByTestId("diagram-canvas");
  for (const name of [/^ROOT/, /^S: simple declarative clause/, /^NP: noun phrase, covering “The child”/]) {
    await expect(canvas.getByRole("button", { name })).toHaveCount(1);
  }
  // the interlinear table lists each word with its category
  const table = page.getByRole("region", { name: "Word-by-word analysis" });
  await expect(table.getByRole("button", { name: "eating", exact: true })).toBeVisible();
  await expect(table.getByText("VERB")).toBeVisible();
});

test("selecting a phrase explains it and identifies the source", async ({ page }) => {
  await page.goto("/");
  await analyze(page, "The child is eating rice.");
  await page
    .getByTestId("diagram-canvas")
    .getByRole("button", { name: /^VP: verb phrase, covering “is eating rice”/ })
    .click();
  await openPanel(page, "Details");
  const details = page.getByRole("complementary", { name: "Details" });
  await expect(details.getByText("“is eating rice”")).toBeVisible();
  await expect(details.getByText(/A phrase headed by a verb/)).toBeVisible();
  await expect(details.getByText("Curated definition")).toBeVisible();
  await expect(details.getByText(/No confidence scores are shown/)).toBeVisible();
});

test("collapses a phrase into a triangle and expands it again", async ({ page }) => {
  await page.goto("/");
  await analyze(page, "The child is eating rice.");
  const canvas = page.getByTestId("diagram-canvas");
  await canvas.getByRole("button", { name: /^NP: noun phrase, covering “The child”/ }).click();
  await openPanel(page, "Details");
  await page.getByRole("button", { name: "Collapse into a triangle" }).click();
  await openPanel(page, "Diagram");
  await expect(canvas.getByRole("button", { name: /^DT: determiner/ })).toHaveCount(0);
  await expect(canvas.locator("polygon")).toHaveCount(1);
  await page.getByRole("button", { name: "Expand all phrases" }).click();
  await expect(canvas.getByRole("button", { name: /^DT: determiner/ })).toHaveCount(1);
});

test("keyboard navigation follows the branches of the tree", async ({ page, browserName }) => {
  test.skip(isMobile(page), "keyboard navigation is a desktop interaction");
  void browserName;
  await page.goto("/");
  await analyze(page, "The child is eating rice.");
  const canvas = page.getByTestId("diagram-canvas");
  await canvas.getByRole("button", { name: /^ROOT/ }).focus();
  await page.keyboard.press("ArrowDown"); // S
  await page.keyboard.press("ArrowDown"); // NP
  await page.keyboard.press("ArrowRight"); // VP
  await page.keyboard.press("Enter");
  await expect(
    canvas.getByRole("button", { name: /^VP: verb phrase, covering “is eating rice”/ }),
  ).toHaveAttribute("aria-pressed", "true");
});

test("shows the dependency graph and explains a relation", async ({ page }) => {
  await page.goto("/");
  await analyze(page, "The child is eating rice.");
  await page.getByRole("button", { name: "Word relations", exact: true }).click();
  const canvas = page.getByTestId("diagram-canvas");
  await expect(canvas.getByRole("button", { name: "child NOUN" })).toBeVisible();
  await canvas.getByText("nsubj", { exact: true }).click();
  await openPanel(page, "Details");
  await expect(page.getByText(/A nominal that is the syntactic subject/)).toBeVisible();

  await openPanel(page, "Diagram");
  await page.getByRole("button", { name: "Hide relation labels" }).click();
  await expect(canvas.getByText("nsubj", { exact: true })).toHaveCount(0);
});

test("exports the visible tree as SVG and PNG", async ({ page }) => {
  await page.goto("/");
  await analyze(page, "The child is eating rice.");

  const [svgDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Download as SVG" }).click(),
  ]);
  expect(svgDownload.suggestedFilename()).toBe(
    "syntaxlab-constituency-the-child-is-eating-rice.svg",
  );
  const svg = await readFile((await svgDownload.path())!, "utf8");
  expect(svg).toContain('xmlns="http://www.w3.org/2000/svg"');
  expect(svg).toMatch(/>eating</);
  expect(svg).toContain("@font-face"); // labels keep their typeface outside the app
  expect(svg).not.toMatch(/data-zoom-layer="[^"]*" transform=/);

  const [pngDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Download as PNG" }).click(),
  ]);
  const png = await readFile((await pngDownload.path())!);
  expect(png.subarray(0, 8)).toEqual(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
});

test("reports API validation errors in plain language", async ({ page }) => {
  await page.goto("/");
  await openPanel(page, "Sentence");
  await page.getByRole("textbox", { name: "Sentence" }).fill("One here. Two here.");
  await page.getByRole("button", { name: "Analyze", exact: true }).click();
  await openPanel(page, "Diagram");
  await expect(page.getByRole("region", { name: "Diagram" }).getByRole("alert")).toHaveText(/Found 2 sentences; analyze up to 1 at a time/);
});

test("explains when the analysis service cannot be reached", async ({ page }) => {
  await page.route(`${API}/api/v1/parse`, (route) => route.abort("connectionrefused"));
  await page.goto("/");
  await openPanel(page, "Sentence");
  await page.getByRole("textbox", { name: "Sentence" }).fill("The child is eating rice.");
  await page.getByRole("button", { name: "Analyze", exact: true }).click();
  await openPanel(page, "Diagram");
  await expect(page.getByRole("region", { name: "Diagram" }).getByRole("alert")).toContainText("Can't reach the analysis service");
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});

test("validates input before sending it", async ({ page }) => {
  await page.goto("/");
  await openPanel(page, "Sentence");
  await page.getByRole("textbox", { name: "Sentence" }).fill("x".repeat(301));
  await expect(page.getByText(/Keep it under 300 characters/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Analyze", exact: true })).toBeDisabled();
});

test("never scrolls the page sideways", async ({ page }) => {
  await page.goto("/");
  await analyze(page, "Did the students not read the book that the professor recommended?");
  const widths = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(widths[0]).toBeLessThanOrEqual(widths[1]);
});
