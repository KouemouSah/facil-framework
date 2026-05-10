import { test as setup, expect } from '@playwright/test';
import path from 'path';

const authFile = path.join(__dirname, '../../playwright/.auth/user.json');

/**
 * Authentication setup for E2E tests
 * Creates authenticated session state to be reused across tests
 */
setup('authenticate as citizen', async ({ page }) => {
  // Navigate to login page
  await page.goto('/es/auth');

  // Fill login form
  await page.getByLabel(/correo electrónico|email/i).fill('test.citizen@taxasge.gq');
  await page.getByLabel(/contraseña|password/i).fill('TestPassword123!');

  // Submit form
  await page.getByRole('button', { name: /iniciar sesión|login|entrar/i }).click();

  // Wait for successful login redirect
  await page.waitForURL('**/dashboard/**');

  // Verify we're logged in
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();

  // Save authentication state
  await page.context().storageState({ path: authFile });
});
