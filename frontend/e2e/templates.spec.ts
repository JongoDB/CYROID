import { test, expect } from '@playwright/test';

test.describe('VM Templates', () => {
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

    // Navigate to templates
    await page.getByRole('link', { name: /templates/i }).click();
    await expect(page).toHaveURL(/templates/);
  });

  test('should display templates page', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /templates/i })).toBeVisible();
  });

  test('should open create template dialog', async ({ page }) => {
    await page.getByRole('button', { name: /create|new|add/i }).click();

    // Dialog should be visible
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByPlaceholder(/name/i)).toBeVisible();
  });

  test('should create a new template', async ({ page }) => {
    await page.getByRole('button', { name: /create|new|add/i }).click();

    const templateName = `Test Template ${Date.now()}`;
    await page.getByPlaceholder(/name/i).fill(templateName);

    // Fill in other required fields if they exist
    const descriptionField = page.getByPlaceholder(/description/i);
    if (await descriptionField.isVisible()) {
      await descriptionField.fill('Test template description');
    }

    const baseImageField = page.getByPlaceholder(/image/i);
    if (await baseImageField.isVisible()) {
      await baseImageField.fill('ubuntu:22.04');
    }

    // Submit the form
    await page.getByRole('button', { name: /create|save|submit/i }).last().click();

    // Template should appear in the list
    await expect(page.getByText(templateName)).toBeVisible();
  });

  test('should edit an existing template', async ({ page }) => {
    // First create a template
    await page.getByRole('button', { name: /create|new|add/i }).click();

    const templateName = `Test Template ${Date.now()}`;
    await page.getByPlaceholder(/name/i).fill(templateName);

    const baseImageField = page.getByPlaceholder(/image/i);
    if (await baseImageField.isVisible()) {
      await baseImageField.fill('ubuntu:22.04');
    }

    await page.getByRole('button', { name: /create|save|submit/i }).last().click();
    await expect(page.getByText(templateName)).toBeVisible();

    // Click edit on the template
    const templateRow = page.getByText(templateName).locator('..');
    await templateRow.getByRole('button', { name: /edit/i }).click();

    // Update the description
    const descriptionField = page.getByPlaceholder(/description/i);
    if (await descriptionField.isVisible()) {
      await descriptionField.fill('Updated description');
    }

    await page.getByRole('button', { name: /save|update/i }).last().click();
  });

  test('should delete a template', async ({ page }) => {
    // First create a template
    await page.getByRole('button', { name: /create|new|add/i }).click();

    const templateName = `Delete Template ${Date.now()}`;
    await page.getByPlaceholder(/name/i).fill(templateName);

    const baseImageField = page.getByPlaceholder(/image/i);
    if (await baseImageField.isVisible()) {
      await baseImageField.fill('ubuntu:22.04');
    }

    await page.getByRole('button', { name: /create|save|submit/i }).last().click();
    await expect(page.getByText(templateName)).toBeVisible();

    // Click delete on the template
    const templateCard = page.getByText(templateName).locator('..').locator('..');
    await templateCard.getByRole('button', { name: /delete/i }).click();

    // Confirm deletion if there's a confirmation dialog
    const confirmButton = page.getByRole('button', { name: /confirm|yes|delete/i });
    if (await confirmButton.isVisible()) {
      await confirmButton.click();
    }

    // Template should be removed
    await expect(page.getByText(templateName)).not.toBeVisible();
  });

  test('should clone a template', async ({ page }) => {
    // First create a template
    await page.getByRole('button', { name: /create|new|add/i }).click();

    const templateName = `Clone Template ${Date.now()}`;
    await page.getByPlaceholder(/name/i).fill(templateName);

    const baseImageField = page.getByPlaceholder(/image/i);
    if (await baseImageField.isVisible()) {
      await baseImageField.fill('ubuntu:22.04');
    }

    await page.getByRole('button', { name: /create|save|submit/i }).last().click();
    await expect(page.getByText(templateName)).toBeVisible();

    // Click clone on the template
    const templateCard = page.getByText(templateName).locator('..').locator('..');
    const cloneButton = templateCard.getByRole('button', { name: /clone|copy|duplicate/i });
    if (await cloneButton.isVisible()) {
      await cloneButton.click();

      // Clone should appear in the list
      await expect(page.getByText(/copy|clone/i)).toBeVisible();
    }
  });
});
