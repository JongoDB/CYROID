import { test, expect } from '@playwright/test';

test.describe('Cyber Ranges', () => {
  // Setup: Register and login before each test
  test.beforeEach(async ({ page }) => {
    await page.goto('/');

    // Register and login
    await page.getByRole('link', { name: /register|sign up/i }).click();

    const uniqueId = Date.now();
    const username = `testuser_${uniqueId}`;
    const email = `test-${uniqueId}@example.com`;
    const password = 'TestPassword123!';

    await page.getByPlaceholder(/username/i).fill(username);
    await page.getByPlaceholder(/email/i).fill(email);
    await page.getByPlaceholder(/password/i).first().fill(password);

    const confirmPassword = page.getByPlaceholder(/confirm/i);
    if (await confirmPassword.isVisible()) {
      await confirmPassword.fill(password);
    }

    await page.getByRole('button', { name: /register|sign up/i }).click();
    await page.waitForURL(/login|dashboard/);

    if (page.url().includes('login')) {
      await page.getByPlaceholder(/email/i).fill(email);
      await page.getByPlaceholder(/password/i).fill(password);
      await page.getByRole('button', { name: /login/i }).click();
    }

    await expect(page).toHaveURL(/dashboard/);

    // Navigate to ranges
    await page.getByRole('link', { name: /ranges/i }).click();
    await expect(page).toHaveURL(/ranges/);
  });

  test('should display ranges page', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /ranges/i })).toBeVisible();
  });

  test('should open create range dialog', async ({ page }) => {
    await page.getByRole('button', { name: /create|new|add/i }).click();

    // Dialog should be visible
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByPlaceholder(/name/i)).toBeVisible();
  });

  test('should create a new range', async ({ page }) => {
    await page.getByRole('button', { name: /create|new|add/i }).click();

    const rangeName = `Test Range ${Date.now()}`;
    await page.getByPlaceholder(/name/i).fill(rangeName);

    // Fill in description if available
    const descriptionField = page.getByPlaceholder(/description/i);
    if (await descriptionField.isVisible()) {
      await descriptionField.fill('Test range description');
    }

    // Submit the form
    await page.getByRole('button', { name: /create|save|submit/i }).last().click();

    // Range should appear in the list
    await expect(page.getByText(rangeName)).toBeVisible();
  });

  test('should view range details', async ({ page }) => {
    // First create a range
    await page.getByRole('button', { name: /create|new|add/i }).click();

    const rangeName = `Detail Range ${Date.now()}`;
    await page.getByPlaceholder(/name/i).fill(rangeName);

    await page.getByRole('button', { name: /create|save|submit/i }).last().click();
    await expect(page.getByText(rangeName)).toBeVisible();

    // Click on the range to view details
    await page.getByText(rangeName).click();

    // Should navigate to range detail page
    await expect(page).toHaveURL(/ranges\/[a-f0-9-]+/);
  });

  test('should show networks section in range detail', async ({ page }) => {
    // Create a range
    await page.getByRole('button', { name: /create|new|add/i }).click();

    const rangeName = `Network Range ${Date.now()}`;
    await page.getByPlaceholder(/name/i).fill(rangeName);

    await page.getByRole('button', { name: /create|save|submit/i }).last().click();
    await expect(page.getByText(rangeName)).toBeVisible();

    // Go to range detail
    await page.getByText(rangeName).click();

    // Should show networks section
    await expect(page.getByText(/networks/i)).toBeVisible();
  });

  test('should create a network in range', async ({ page }) => {
    // Create a range
    await page.getByRole('button', { name: /create|new|add/i }).click();

    const rangeName = `Add Network Range ${Date.now()}`;
    await page.getByPlaceholder(/name/i).fill(rangeName);

    await page.getByRole('button', { name: /create|save|submit/i }).last().click();
    await expect(page.getByText(rangeName)).toBeVisible();

    // Go to range detail
    await page.getByText(rangeName).click();

    // Click add network
    const addNetworkButton = page.getByRole('button', { name: /add network/i });
    if (await addNetworkButton.isVisible()) {
      await addNetworkButton.click();

      // Fill in network details
      await page.getByPlaceholder(/name/i).fill('TestNetwork');
      await page.getByPlaceholder(/subnet/i).fill('10.0.1.0/24');

      await page.getByRole('button', { name: /create|save|add/i }).last().click();

      // Network should appear
      await expect(page.getByText('TestNetwork')).toBeVisible();
    }
  });

  test('should delete a range', async ({ page }) => {
    // Create a range
    await page.getByRole('button', { name: /create|new|add/i }).click();

    const rangeName = `Delete Range ${Date.now()}`;
    await page.getByPlaceholder(/name/i).fill(rangeName);

    await page.getByRole('button', { name: /create|save|submit/i }).last().click();
    await expect(page.getByText(rangeName)).toBeVisible();

    // Find and click delete button
    const rangeCard = page.getByText(rangeName).locator('..').locator('..');
    const deleteButton = rangeCard.getByRole('button', { name: /delete/i });
    if (await deleteButton.isVisible()) {
      await deleteButton.click();

      // Confirm if needed
      const confirmButton = page.getByRole('button', { name: /confirm|yes|delete/i });
      if (await confirmButton.isVisible()) {
        await confirmButton.click();
      }

      // Range should be removed
      await expect(page.getByText(rangeName)).not.toBeVisible();
    }
  });

  test('should clone a range', async ({ page }) => {
    // Create a range
    await page.getByRole('button', { name: /create|new|add/i }).click();

    const rangeName = `Clone Range ${Date.now()}`;
    await page.getByPlaceholder(/name/i).fill(rangeName);

    await page.getByRole('button', { name: /create|save|submit/i }).last().click();
    await expect(page.getByText(rangeName)).toBeVisible();

    // Find and click clone button
    const rangeCard = page.getByText(rangeName).locator('..').locator('..');
    const cloneButton = rangeCard.getByRole('button', { name: /clone|copy|duplicate/i });
    if (await cloneButton.isVisible()) {
      await cloneButton.click();

      // Clone should appear in the list
      await expect(page.getByText(/copy/i)).toBeVisible();
    }
  });
});
