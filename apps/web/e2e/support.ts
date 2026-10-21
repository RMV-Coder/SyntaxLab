import { readFileSync } from "node:fs";
import path from "node:path";

import type { Page, Route } from "@playwright/test";

/** Must match NEXT_PUBLIC_SYNTAXLAB_API_URL in playwright.config.ts. */
export const API = "http://api.syntaxlab.test";

const fixture = (name: string) =>
  readFileSync(path.join(__dirname, "fixtures", `${name}.json`), "utf8");

/** Parse responses recorded from the real parser, keyed by the sentence. */
const PARSES: Record<string, string> = {
  "The child is eating rice.": "parse-child",
  "I saw the man with a telescope.": "parse-telescope",
  "Did the students not read the book that the professor recommended?": "parse-question",
};

const json = (route: Route, body: string, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body });

export async function mockApi(page: Page, options: { parseDelayMs?: number } = {}) {
  await page.route(`${API}/api/v1/languages`, (route) => json(route, fixture("languages")));
  await page.route(`${API}/api/v1/languages/en`, (route) => json(route, fixture("language-en")));
  await page.route(`${API}/api/v1/schemes/*`, (route) => {
    const id = route.request().url().split("/").pop()!;
    return json(route, fixture(`scheme-${id}`));
  });
  await page.route(`${API}/api/v1/parse`, async (route) => {
    const body = route.request().postDataJSON() as { text: string };
    if (options.parseDelayMs) await new Promise((r) => setTimeout(r, options.parseDelayMs));
    const name = PARSES[body.text.trim()];
    if (name) return json(route, fixture(name));
    if (body.text.includes(". ")) return json(route, fixture("error-two-sentences"), 422);
    return json(
      route,
      JSON.stringify({ error: { code: "engine_failure", message: "No recorded fixture." } }),
      500,
    );
  });
}
