import { test, expect } from '@playwright/test';

test.describe('Workflow Wizard', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to service requests page
    await page.goto('/es/dashboard/services');
  });

  test('displays workflow wizard with steps', async ({ page }) => {
    // Click new request button
    await page.getByRole('button', { name: /nueva solicitud|new request/i }).click();

    // Select a workflow type (e.g., Passport)
    await page.getByRole('button', { name: /pasaporte nuevo/i }).click();

    // Verify wizard is displayed
    await expect(page.getByText(/paso 1|step 1/i)).toBeVisible();

    // Verify progress indicator exists
    await expect(page.locator('[data-testid="wizard-progress"]')).toBeVisible();
  });

  test('navigates between steps using next/previous buttons', async ({ page }) => {
    // Start a new request
    await page.getByRole('button', { name: /nueva solicitud/i }).click();
    await page.getByRole('button', { name: /pasaporte nuevo/i }).click();

    // Complete step 1 (identity verification)
    await page.getByRole('button', { name: /siguiente|next/i }).click();

    // Verify we're on step 2
    await expect(page.getByText(/paso 2|step 2/i)).toBeVisible();

    // Go back to step 1
    await page.getByRole('button', { name: /anterior|previous/i }).click();

    // Verify we're back on step 1
    await expect(page.getByText(/paso 1|step 1/i)).toBeVisible();
  });

  test('shows step icons based on step type', async ({ page }) => {
    await page.getByRole('button', { name: /nueva solicitud/i }).click();
    await page.getByRole('button', { name: /pasaporte nuevo/i }).click();

    // Verify step icons are present (at least 3 steps)
    const stepIndicators = page.locator('[data-testid^="step-indicator-"]');
    const count = await stepIndicators.count();
    expect(count).toBeGreaterThanOrEqual(3);
  });

  test('can save draft and continue later', async ({ page }) => {
    await page.getByRole('button', { name: /nueva solicitud/i }).click();
    await page.getByRole('button', { name: /pasaporte nuevo/i }).click();

    // Save draft
    await page.getByRole('button', { name: /guardar borrador|save draft/i }).click();

    // Verify success notification
    await expect(page.getByText(/borrador guardado|draft saved/i)).toBeVisible();

    // Navigate away and back
    await page.goto('/es/dashboard/services');

    // Find draft in list
    await expect(page.getByText(/borrador/i)).toBeVisible();
  });

  test('displays validation errors when required fields are empty', async ({ page }) => {
    await page.getByRole('button', { name: /nueva solicitud/i }).click();
    await page.getByRole('button', { name: /pasaporte nuevo/i }).click();

    // Try to submit without required documents
    await page.getByRole('button', { name: /enviar|submit/i }).click();

    // Verify validation error appears
    await expect(page.getByText(/obligatorio|required/i)).toBeVisible();
  });

  test('shows correct workflow category label', async ({ page }) => {
    await page.getByRole('button', { name: /nueva solicitud/i }).click();

    // Verify category labels are displayed
    await expect(page.getByText(/identidad|identity/i)).toBeVisible();
    await expect(page.getByText(/vehículos|vehicles/i)).toBeVisible();
    await expect(page.getByText(/extranjería|immigration/i)).toBeVisible();
  });
});
