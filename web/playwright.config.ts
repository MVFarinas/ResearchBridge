/**
 * Playwright smoke tests (`npm run test:e2e`). They run against a running
 * stack: the backend with an ingested corpus and the web app (by default
 * `next start` on port 3045, see docs/phase-notes/phase-4-5.md), so they are
 * not part of `npm test` or CI. Browsers are installed into node_modules with
 * `PLAYWRIGHT_BROWSERS_PATH=0 npx playwright install --only-shell chromium`.
 */
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  reporter: "list",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:3045",
    trace: "off",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "phone", use: { ...devices["Pixel 7"] } },
  ],
});
