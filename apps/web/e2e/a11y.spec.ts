import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { mockApi, mockLabApi, mockLearnApi } from "./support";

/** WCAG 2.0/2.1/2.2 level A and AA rules. Every violation fails the test. */
async function audit(page: Page, name: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const summary = results.violations.map(
    (v) => `${v.id} (${v.impact}): ${v.help}\n  ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join("\n  ")}`,
  );
  expect(summary, `${name}\n${summary.join("\n")}`).toEqual([]);
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await mockLabApi(page);
  await mockLearnApi(page);
});

test("analyzer: empty and with an analysis", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("combobox", { name: "Language" })).toHaveText(/English/);
  await audit(page, "analyzer (empty)");
  if ((page.viewportSize()?.width ?? 1280) < 1024) return; // panels are tested on desktop
  await page.getByRole("textbox", { name: "Sentence" }).fill("The child is eating rice.");
  await page.getByRole("button", { name: "Analyze", exact: true }).click();
  await page
    .getByTestId("diagram-canvas")
    .getByRole("button", { name: /^VP: verb phrase, covering “is eating rice”/ })
    .click();
  await audit(page, "analyzer (constituency, node selected)");
  await page.getByRole("button", { name: "Word relations", exact: true }).click();
  await audit(page, "analyzer (dependency)");
});

test("algorithm lab: replay and outcome", async ({ page }) => {
  await page.goto("/lab");
  await expect(page.getByRole("textbox", { name: "Rules" })).toHaveValue(/NP PP/);
  await audit(page, "lab (grammar)");
  await page.getByRole("textbox", { name: "Sentence" }).fill("I saw the man with a telescope");
  await page.getByRole("button", { name: "Parse", exact: true }).click();
  await expect(page.getByTestId("step-explanation")).toContainText("Step 1");
  for (let i = 0; i < 20; i++) await page.getByRole("button", { name: "Step forward" }).click();
  // Audit a settled page, not one mid-update.
  await expect(page.getByTestId("step-explanation")).toContainText("Step 21:");
  await audit(page, "lab (mid replay)");
  await page.getByRole("button", { name: "Jump to the end" }).click();
  await expect(page.getByTestId("step-explanation")).toContainText("Accepted");
  await audit(page, "lab (outcome)");
});

test("practice: list and every exercise type", async ({ page }) => {
  for (const path of ["/learn", "/learn/ud-en-pos-01", "/learn/ud-en-dependency-01", "/learn/grammar-01"]) {
    await page.goto(path);
    await expect(page.locator("h1")).toBeVisible();
    await expect(page.getByText("Loading")).toHaveCount(0);
    await audit(page, path);
  }
});

test("about", async ({ page }) => {
  await page.goto("/about");
  await audit(page, "about");
});
