import { test, expect } from '@playwright/test';

test.describe('Agent Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Login as agent and navigate to dashboard
    await page.goto('/es/dashboard/agent/requests');
  });

  test('displays statistics cards', async ({ page }) => {
    // Verify stats cards are visible
    await expect(page.getByText(/total de solicitudes|total requests/i)).toBeVisible();
    await expect(page.getByText(/aprobadas hoy|approved today/i)).toBeVisible();
    await expect(page.getByText(/rechazadas hoy|rejected today/i)).toBeVisible();
    await expect(page.getByText(/pendientes de revisión|pending review/i)).toBeVisible();
  });

  test('displays requests table', async ({ page }) => {
    // Verify table headers
    await expect(page.getByRole('columnheader', { name: /id/i })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: /ciudadano|citizen/i })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: /servicio|service/i })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: /estado|status/i })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: /acciones|actions/i })).toBeVisible();
  });

  test('can filter by status', async ({ page }) => {
    // Click status filter
    await page.getByRole('combobox', { name: /estado|status/i }).click();

    // Select "Pending" filter
    await page.getByRole('option', { name: /pendiente|pending/i }).click();

    // Verify filter is applied (URL or visual indicator)
    await expect(page.getByRole('combobox', { name: /estado|status/i })).toContainText(
      /pendiente|pending/i
    );
  });

  test('can filter by priority', async ({ page }) => {
    // Click priority filter
    await page.getByRole('combobox', { name: /prioridad|priority/i }).click();

    // Select "Urgent" filter
    await page.getByRole('option', { name: /urgente|urgent/i }).click();

    // Verify filter is applied
    await expect(page.getByRole('combobox', { name: /prioridad|priority/i })).toContainText(
      /urgente|urgent/i
    );
  });

  test('can search requests', async ({ page }) => {
    // Type in search box
    await page.getByPlaceholder(/buscar|search/i).fill('PASAPORTE');

    // Verify search results update
    await page.waitForTimeout(500); // Wait for debounce

    // Results should show only passport-related requests
    const tableRows = page.locator('tbody tr');
    const count = await tableRows.count();

    if (count > 0) {
      // All visible rows should contain "PASAPORTE"
      for (let i = 0; i < Math.min(count, 5); i++) {
        const row = tableRows.nth(i);
        await expect(row).toContainText(/pasaporte/i);
      }
    }
  });

  test('shows quick action buttons on each row', async ({ page }) => {
    const firstRow = page.locator('tbody tr').first();

    if (await firstRow.isVisible()) {
      // Verify action buttons are present
      await expect(firstRow.getByRole('button', { name: /aprobar|approve/i })).toBeVisible();
      await expect(firstRow.getByRole('button', { name: /rechazar|reject/i })).toBeVisible();
      await expect(firstRow.getByRole('button', { name: /ver|view/i })).toBeVisible();
    }
  });

  test('opens approve confirmation dialog', async ({ page }) => {
    const approveButton = page.locator('tbody tr').first().getByRole('button', { name: /aprobar|approve/i });

    if (await approveButton.isVisible()) {
      await approveButton.click();

      // Verify dialog opens
      await expect(page.locator('[role="dialog"]')).toBeVisible();
      await expect(page.getByText(/confirmar aprobación|confirm approval/i)).toBeVisible();

      // Close dialog
      await page.getByRole('button', { name: /cancelar|cancel/i }).click();
    }
  });

  test('opens reject dialog with reason field', async ({ page }) => {
    const rejectButton = page.locator('tbody tr').first().getByRole('button', { name: /rechazar|reject/i });

    if (await rejectButton.isVisible()) {
      await rejectButton.click();

      // Verify dialog opens with reason field
      await expect(page.locator('[role="dialog"]')).toBeVisible();
      await expect(page.getByLabel(/motivo|reason/i)).toBeVisible();

      // Close dialog
      await page.getByRole('button', { name: /cancelar|cancel/i }).click();
    }
  });

  test('navigates to request detail on row click', async ({ page }) => {
    const firstRow = page.locator('tbody tr').first();

    if (await firstRow.isVisible()) {
      // Click on view details button
      await firstRow.getByRole('button', { name: /ver detalles|view details/i }).click();

      // Verify navigation to detail page
      await expect(page).toHaveURL(/.*\/requests\/\d+/);
    }
  });

  test('can clear all filters', async ({ page }) => {
    // Apply some filters
    await page.getByRole('combobox', { name: /estado|status/i }).click();
    await page.getByRole('option', { name: /pendiente|pending/i }).click();

    // Click clear filters button
    await page.getByRole('button', { name: /limpiar filtros|clear filters/i }).click();

    // Verify filters are cleared
    await expect(page.getByRole('combobox', { name: /estado|status/i })).not.toContainText(
      /pendiente|pending/i
    );
  });

  test('shows loading state while fetching data', async ({ page }) => {
    // Intercept API request to delay response
    await page.route('**/api/v1/service-requests**', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await route.continue();
    });

    // Reload page
    await page.reload();

    // Verify loading indicator appears
    await expect(page.getByText(/cargando|loading/i)).toBeVisible();
  });

  test('shows empty state when no requests', async ({ page }) => {
    // Mock empty response
    await page.route('**/api/v1/service-requests**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: [], meta: { total: 0 } }),
      });
    });

    // Reload page
    await page.reload();

    // Verify empty state message
    await expect(page.getByText(/no hay solicitudes|no requests/i)).toBeVisible();
  });
});
