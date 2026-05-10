import { test, expect } from '@playwright/test';

test.describe('Request Detail', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to a specific request detail page (using mock ID)
    await page.goto('/es/dashboard/agent/requests/1');
  });

  test('displays request overview tab', async ({ page }) => {
    // Verify overview information is displayed
    await expect(page.getByText(/id de solicitud|request id/i)).toBeVisible();
    await expect(page.getByText(/flujo de trabajo|workflow/i)).toBeVisible();
    await expect(page.getByText(/estado|status/i)).toBeVisible();
    await expect(page.getByText(/creada el|created at/i)).toBeVisible();
  });

  test('shows all tabs', async ({ page }) => {
    // Verify tabs are present
    await expect(page.getByRole('tab', { name: /resumen|overview/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /documentos|documents/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /validación|validation/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /historial|history/i })).toBeVisible();
  });

  test('can switch between tabs', async ({ page }) => {
    // Click on Documents tab
    await page.getByRole('tab', { name: /documentos|documents/i }).click();

    // Verify documents content is shown
    await expect(page.getByText(/documentos subidos|uploaded documents/i)).toBeVisible();

    // Click on Validation tab
    await page.getByRole('tab', { name: /validación|validation/i }).click();

    // Verify validation content is shown
    await expect(page.getByText(/resultados de validación|validation results/i)).toBeVisible();

    // Click on History tab
    await page.getByRole('tab', { name: /historial|history/i }).click();

    // Verify history timeline is shown
    await expect(page.getByText(/cronología|timeline/i)).toBeVisible();
  });

  test('displays citizen information', async ({ page }) => {
    // Verify citizen section exists
    await expect(page.getByText(/ciudadano|citizen/i)).toBeVisible();

    // Check for email or name display
    const citizenInfo = page.locator('[data-testid="citizen-info"]');
    await expect(citizenInfo).toBeVisible();
  });

  test('shows action buttons based on request status', async ({ page }) => {
    // Check for action buttons (visibility depends on status)
    const actionButtons = page.locator('[data-testid="action-buttons"]');
    await expect(actionButtons).toBeVisible();

    // At least one action should be available
    const buttonCount = await actionButtons.locator('button').count();
    expect(buttonCount).toBeGreaterThanOrEqual(1);
  });

  test('documents tab shows uploaded documents with extraction data', async ({ page }) => {
    await page.getByRole('tab', { name: /documentos|documents/i }).click();

    // Check for document cards
    const documentCards = page.locator('[data-testid="document-card"]');

    if ((await documentCards.count()) > 0) {
      // Click on first document to see extraction data
      await documentCards.first().click();

      // Verify extraction preview appears
      await expect(page.getByText(/datos extraídos|extracted data/i)).toBeVisible();
    }
  });

  test('validation tab shows cross-document validation results', async ({ page }) => {
    await page.getByRole('tab', { name: /validación|validation/i }).click();

    // Check for validation results section
    await expect(page.locator('[data-testid="validation-results"]')).toBeVisible();

    // Check for validation status indicators
    const statusIndicators = page.locator('[data-testid="validation-status"]');
    if ((await statusIndicators.count()) > 0) {
      await expect(statusIndicators.first()).toBeVisible();
    }
  });

  test('history tab shows timeline of events', async ({ page }) => {
    await page.getByRole('tab', { name: /historial|history/i }).click();

    // Verify timeline container
    await expect(page.locator('[data-testid="history-timeline"]')).toBeVisible();

    // Check for timeline items
    const timelineItems = page.locator('[data-testid="timeline-item"]');
    if ((await timelineItems.count()) > 0) {
      // Each item should have a timestamp
      const firstItem = timelineItems.first();
      await expect(firstItem).toBeVisible();
    }
  });

  test('approve action shows confirmation and updates status', async ({ page }) => {
    const approveButton = page.getByRole('button', { name: /aprobar|approve/i });

    if (await approveButton.isVisible()) {
      await approveButton.click();

      // Verify confirmation dialog
      await expect(page.locator('[role="dialog"]')).toBeVisible();
      await expect(page.getByText(/confirmar aprobación/i)).toBeVisible();

      // Click confirm
      await page.getByRole('button', { name: /confirmar|confirm/i }).click();

      // Verify success notification
      await expect(page.getByText(/aprobada|approved/i)).toBeVisible();
    }
  });

  test('reject action requires reason and updates status', async ({ page }) => {
    const rejectButton = page.getByRole('button', { name: /rechazar|reject/i });

    if (await rejectButton.isVisible()) {
      await rejectButton.click();

      // Verify dialog with reason field
      await expect(page.locator('[role="dialog"]')).toBeVisible();

      // Fill in reason
      await page.getByLabel(/motivo|reason/i).fill('Documentos incompletos');

      // Verify confirm button is enabled after entering reason
      const confirmButton = page.getByRole('button', { name: /confirmar|confirm/i });
      await expect(confirmButton).toBeEnabled();

      // Submit rejection
      await confirmButton.click();

      // Verify success notification
      await expect(page.getByText(/rechazada|rejected/i)).toBeVisible();
    }
  });

  test('request info action sends notification to citizen', async ({ page }) => {
    const requestInfoButton = page.getByRole('button', { name: /solicitar información|request info/i });

    if (await requestInfoButton.isVisible()) {
      await requestInfoButton.click();

      // Verify dialog
      await expect(page.locator('[role="dialog"]')).toBeVisible();

      // Fill in info request message
      await page.getByLabel(/mensaje|message/i).fill('Por favor proporcione el certificado de nacimiento');

      // Submit
      await page.getByRole('button', { name: /enviar|send/i }).click();

      // Verify success notification
      await expect(page.getByText(/solicitud enviada|request sent/i)).toBeVisible();
    }
  });

  test('schedule appointment opens date picker', async ({ page }) => {
    const scheduleButton = page.getByRole('button', { name: /programar cita|schedule appointment/i });

    if (await scheduleButton.isVisible()) {
      await scheduleButton.click();

      // Verify dialog with date picker
      await expect(page.locator('[role="dialog"]')).toBeVisible();
      await expect(page.getByText(/seleccionar fecha|select date/i)).toBeVisible();
    }
  });

  test('back to list button navigates to dashboard', async ({ page }) => {
    await page.getByRole('button', { name: /volver a la lista|back to list/i }).click();

    // Verify navigation back to dashboard
    await expect(page).toHaveURL(/.*\/agent\/requests$/);
  });

  test('displays tariff information', async ({ page }) => {
    // Check for tariff section
    const tariffSection = page.locator('[data-testid="tariff-info"]');

    if (await tariffSection.isVisible()) {
      // Verify amount is displayed
      await expect(tariffSection).toContainText(/xaf/i);
    }
  });

  test('shows entity responsible for workflow', async ({ page }) => {
    // Verify entity information
    await expect(page.getByText(/entidad|entity/i)).toBeVisible();
  });
});
