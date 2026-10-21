import { defineConfig, devices } from "@playwright/test";

/**
 * E2E tests run against the real Next.js app. API calls are intercepted with recorded
 * responses from the real parser (e2e/fixtures), so the suite runs without NLP models; the
 * model-backed path is covered by the backend's `pytest -m models` suite.
 */
const PORT = Number(process.env.E2E_PORT ?? 3100);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    command: process.env.CI ? `pnpm start --port ${PORT}` : `pnpm dev --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: { NEXT_PUBLIC_SYNTAXLAB_API_URL: "http://api.syntaxlab.test" },
  },
});
