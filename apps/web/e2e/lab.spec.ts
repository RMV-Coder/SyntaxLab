import { expect, test, type Page } from "@playwright/test";

import { mockLabApi } from "./support";

const isMobile = (page: Page) => (page.viewportSize()?.width ?? 1280) < 1024;

async function openPanel(page: Page, name: "Grammar" | "Steps" | "Result") {
  if (isMobile(page)) await page.getByRole("button", { name, exact: true }).click();
}

const explanation = (page: Page) => page.getByTestId("step-explanation");

async function parseExample(page: Page, sentence: string) {
  await page.goto("/lab");
  await expect(page.getByRole("combobox", { name: "Grammar" })).toHaveText(
    /Prepositional-phrase attachment/,
  );
  const input = page.getByRole("textbox", { name: "Sentence" });
  await input.fill(sentence);
  await page.getByRole("button", { name: "Parse", exact: true }).click();
  await expect(explanation(page)).toContainText("Step 1: Start");
}

test.beforeEach(async ({ page }) => {
  await mockLabApi(page);
});

test("loads the preset grammar with verified example outcomes", async ({ page }) => {
  await page.goto("/lab");
  await expect(page.getByRole("textbox", { name: "Rules" })).toHaveValue(/NP\s+-> Pronoun \| Det N \| NP PP/);
  await expect(page.getByText("22 rules, 9 categories, 15 words. Start symbol S.")).toBeVisible();
  await expect(page.getByRole("button", { name: /I saw the man with a telescope\s*2 parses/ })).toBeVisible();
});

test("steps forward and backward through the recorded execution", async ({ page }) => {
  await parseExample(page, "I saw the man with a telescope");
  await expect(explanation(page)).toContainText("adds γ → • S at position 0");
  await page.getByRole("button", { name: "Step forward" }).click();
  await expect(explanation(page)).toContainText("Step 2: Predict S");
  await expect(page.getByRole("region", { name: "Earley chart" }).getByText("S → • NP VP")).toBeVisible();
  await page.getByRole("button", { name: "Step back" }).click();
  await expect(explanation(page)).toContainText("Step 1: Start");
  await expect(page.getByRole("region", { name: "Earley chart" }).getByText("S → • NP VP")).toHaveCount(0);
});

test("reveals the outcome at the end and links trees back to the chart", async ({ page }) => {
  await parseExample(page, "I saw the man with a telescope");
  await openPanel(page, "Result");
  await expect(page.getByText(/outcome appears when the replay reaches the end/)).toBeVisible();
  await page.getByRole("button", { name: "Show the outcome now" }).click();
  await expect(page.getByText("Accepted", { exact: true })).toBeVisible();
  await expect(page.getByText("Tree 1 of 2")).toBeVisible();
  await page.getByRole("button", { name: "Next tree" }).click();
  await expect(page.getByText("Tree 2 of 2")).toBeVisible();

  await page.getByTestId("lab-tree").getByRole("button", { name: "PP, words 5 to 7" }).click();
  await expect(page.getByText(/covers “with a telescope”, built with the rule PP → P NP/)).toBeVisible();
  await page.getByRole("button", { name: "Show the step where it was completed" }).click();
  await openPanel(page, "Steps");
  await expect(explanation(page)).toContainText("Complete NP");
  await expect(explanation(page)).toContainText("PP → P NP •");
});

test("explains why a sentence is rejected", async ({ page }) => {
  await parseExample(page, "I saw the man with");
  await page.getByRole("button", { name: "Jump to the end" }).click();
  await expect(explanation(page)).toContainText("Rejected");
  await expect(explanation(page)).toContainText("does not generate it");
});

test("keyboard shortcuts move through the steps", async ({ page }) => {
  test.skip(isMobile(page), "keyboard shortcuts are a desktop interaction");
  await parseExample(page, "I saw the man with a telescope");
  await page.getByRole("button", { name: "Step forward" }).focus();
  await page.keyboard.press("End");
  await expect(explanation(page)).toContainText("Step 126: Accepted");
  await page.keyboard.press("Home");
  await expect(explanation(page)).toContainText("Step 1: Start");
});

test("reports grammar errors with line numbers and blocks parsing", async ({ page }) => {
  await page.goto("/lab");
  const rules = page.getByRole("textbox", { name: "Rules" });
  await expect(rules).toHaveValue(/NP PP/);
  await rules.fill("S -> NP VP");
  await expect(page.getByRole("button", { name: /^Line 1: NP is used in S → NP VP but has no rules/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Parse", exact: true })).toBeDisabled();
  // Example outcomes are only shown for the unedited preset they were verified against.
  await expect(page.getByText("2 parses", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Restore preset" }).click();
  await expect(rules).toHaveValue(/NP PP/);
});

test("never scrolls the page sideways, even with a wide chart", async ({ page }) => {
  await parseExample(page, "I saw the man with a telescope");
  await page.getByRole("button", { name: "Jump to the end" }).click();
  const widths = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(widths[0]).toBeLessThanOrEqual(widths[1]);
});
