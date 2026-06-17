import { expect, test } from "@playwright/test";

/**
 * Smoke e2e — the login screen renders. Robust to copy/labels (asserts the
 * password field + a submit). Expand with auth + admin flows once a CI job
 * brings up the stack (see playwright.config.ts).
 */
test("login page renders the sign-in form", async ({ page }) => {
  await page.goto("/login");
  await expect(page.locator('input[type="password"]')).toBeVisible();
  await expect(page.getByRole("button", { name: /sign in|se connecter|iniciar/i })).toBeVisible();
});
