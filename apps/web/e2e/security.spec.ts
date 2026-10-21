import { expect, test, type Page } from "@playwright/test";

import { mockApi, mockLabApi } from "./support";

/** Collects Content-Security-Policy violations reported by the page. */
async function recordViolations(page: Page) {
  await page.addInitScript(() => {
    const seen: string[] = [];
    (window as unknown as { __cspViolations: string[] }).__cspViolations = seen;
    document.addEventListener("securitypolicyviolation", (event) => {
      seen.push(`${event.violatedDirective} ${event.blockedURI}`);
    });
  });
  return () => page.evaluate(() => (window as unknown as { __cspViolations: string[] }).__cspViolations);
}

test("pages are served with security headers", async ({ page }) => {
  const response = await page.goto("/");
  const headers = response!.headers();
  const csp = headers["content-security-policy"];
  expect(csp).toContain("default-src 'self'");
  expect(csp).toContain("connect-src 'self' http://api.syntaxlab.test");
  expect(csp).toContain("frame-ancestors 'none'");
  expect(csp).toContain("object-src 'none'");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
});

test("the policy blocks nothing the app needs, including export", async ({ page }) => {
  await mockApi(page);
  await mockLabApi(page);
  const violations = await recordViolations(page);
  await page.goto("/");
  if ((page.viewportSize()?.width ?? 1280) < 1024) {
    await page.getByRole("button", { name: "Sentence", exact: true }).click();
  }
  await page.getByRole("textbox", { name: "Sentence" }).fill("The child is eating rice.");
  await page.getByRole("button", { name: "Analyze", exact: true }).click();
  await expect(page.getByTestId("diagram-canvas")).toBeVisible();
  await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Download as PNG" }).click(),
  ]);
  expect(await violations()).toEqual([]);
  await page.goto("/lab"); // a new document: the record starts again
  await expect(page.getByRole("textbox", { name: "Rules" })).not.toBeEmpty();
  expect(await violations()).toEqual([]);
});
