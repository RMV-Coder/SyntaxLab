import { expect, test, type Page } from "@playwright/test";

import { API, mockApi } from "./support";

const isMobile = (page: Page) => (page.viewportSize()?.width ?? 1280) < 1024;
const SENTENCE = "Binili ng mangingisda ang bangka.";

async function openPanel(page: Page, name: "Sentence" | "Diagram" | "Details") {
  if (isMobile(page)) await page.getByRole("button", { name, exact: true }).click();
}

async function chooseLanguage(page: Page, name: string) {
  await openPanel(page, "Sentence");
  await page.getByRole("combobox", { name: "Language" }).click();
  await page.getByRole("option", { name }).click();
}

async function analyze(page: Page) {
  await page.getByRole("textbox", { name: "Sentence" }).fill(SENTENCE);
  await page.getByRole("button", { name: "Analyze", exact: true }).click();
  await expect(page.getByTestId("diagram-canvas")).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await expect(page.getByRole("combobox", { name: "Language" })).toHaveText(/English/);
  await chooseLanguage(page, "Filipino (Tagalog)");
  await expect(page.getByRole("combobox", { name: "Language" })).toHaveText("Filipino (Tagalog)");
});

test("offers only what the Filipino models produce", async ({ page }) => {
  await expect(page.getByRole("checkbox", { name: /Word relations/ })).toBeVisible();
  await expect(page.getByText("Phrase structure", { exact: true })).toHaveCount(0);
  await expect(page.getByText(SENTENCE)).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Sentence" })).toHaveAttribute(
    "placeholder",
    SENTENCE,
  );
  await expect(page.getByRole("textbox", { name: "Sentence" })).toHaveAttribute("lang", "tl");
});

test("describes only the analyses this language has", async ({ page }) => {
  await openPanel(page, "Diagram");
  await expect(page.getByText(/A dependency graph links every word/)).toBeVisible();
  await expect(page.getByText(/A phrase-structure tree groups/)).toHaveCount(0);
});

test("shows word relations straight away, with no tree to switch to", async ({ page }) => {
  await analyze(page);
  const canvas = page.getByTestId("diagram-canvas");
  await expect(canvas).toHaveAttribute("lang", "tl");
  await expect(canvas.getByRole("button", { name: "mangingisda NOUN" })).toBeVisible();
  await expect(canvas.getByText("obj:agent", { exact: true })).toBeVisible();
  await expect(page.getByRole("group", { name: "Diagram view" })).toHaveCount(0);
});

test("explains Tagalog relations and marks teaching notes as drafts", async ({ page }) => {
  await analyze(page);
  const canvas = page.getByTestId("diagram-canvas");

  await canvas.getByText("obj:agent", { exact: true }).click();
  await openPanel(page, "Details");
  await expect(page.getByText(/the actor of a clause whose verb is not in/)).toBeVisible();

  await openPanel(page, "Diagram");
  await canvas.getByText("nsubj", { exact: true }).click();
  await openPanel(page, "Details");
  await expect(page.getByText(/It is not equivalent to the English subject/)).toBeVisible();
  await expect(page.getByText("Draft, pending review")).toBeVisible();
});

test("shows the note about voice beside the verb's features", async ({ page }) => {
  await analyze(page);
  await page.getByTestId("diagram-canvas").getByRole("button", { name: /^Binili/ }).click();
  await openPanel(page, "Details");
  await expect(page.getByText(/UD Tagalog annotates patient voice as Pass/)).toBeVisible();
  await expect(page.getByText(/The contemplative/)).toBeVisible();
});

test("states the limitations and where the analysis came from", async ({ page }) => {
  await analyze(page);
  await page.getByTestId("diagram-canvas").getByRole("button", { name: /^Binili/ }).click();
  await openPanel(page, "Details");
  await expect(page.getByText(/no parser or treebank for them exists/)).toBeVisible();
  await expect(page.getByText(/UAS 93\.6, LAS 76\.8/)).toBeVisible();
  await expect(page.getByText(/spacy:tl_calamancy_md:0\.2\.0/)).toBeVisible();
});

test("reports two sentences instead of parsing them as one, where it can be seen", async ({
  page,
}) => {
  await page.getByRole("textbox", { name: "Sentence" }).fill("Gumising ang bata. Natulog ang nanay.");
  await page.getByRole("button", { name: "Analyze", exact: true }).click();
  // No panel switch here: on a phone the error must come into view by itself.
  const alert = page.getByRole("region", { name: "Diagram" }).getByRole("alert");
  await expect(alert).toBeVisible();
  await expect(alert).toContainText("sentences");
});

test("switching language clears the analysis and restores its options", async ({ page }) => {
  await analyze(page);
  await chooseLanguage(page, "English");
  await expect(page.getByText("Phrase structure", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Binili ng mangingisda/ })).toHaveCount(0);
  await expect(page.getByText("I saw the man with a telescope.")).toBeVisible();
  await openPanel(page, "Diagram");
  await expect(page.getByTestId("diagram-canvas")).toHaveCount(0);
});

test("a result that arrives after switching language is ignored", async ({ page }) => {
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.unroute(`${API}/api/v1/parse`);
  await page.route(`${API}/api/v1/parse`, async (route) => {
    await held;
    await route.abort().catch(() => undefined);
  });
  await page.getByRole("textbox", { name: "Sentence" }).fill(SENTENCE);
  await page.getByRole("button", { name: "Analyze", exact: true }).click();
  await chooseLanguage(page, "English");
  release();
  await expect(page.getByRole("button", { name: "Analyze", exact: true })).toBeVisible();
  await openPanel(page, "Diagram");
  await expect(page.getByTestId("diagram-canvas")).toHaveCount(0);
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
});
