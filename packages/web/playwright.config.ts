import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright e2e config. Runs against a RUNNING app (set E2E_BASE_URL, default
 * http://localhost:3000). No `webServer` here on purpose: the app's BFF proxies
 * to the backend, so e2e needs the full stack up. Locally: start the stack +
 * `npm run dev:web`, then `E2E_BASE_URL=... npm run test:e2e --workspace=web`.
 * A dedicated CI job (docker-compose stack + `npx playwright install`) is the
 * follow-up — e2e is NOT part of the default CI gate yet.
 */
export default defineConfig({
  testDir: "./e2e",
  // Real-backend e2e: these specs drive multi-step flows (login → Studio create
  // → Site create → reload → assert) against a live stack. 30s was too tight —
  // a cold CI server (or next dev's first-hit route compile locally) pushes the
  // heaviest test just past it, even though every functional step succeeds. 90s
  // gives headroom without masking a genuine hang (a real deadlock still fails).
  timeout: 90_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  reporter: "list",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
