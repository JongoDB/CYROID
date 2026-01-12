import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  // Setup: Register and login before each test
  test.beforeEach(async ({ page }) => {
    await page.goto('/');

    // Register a new user
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
  });

  test('should display dashboard with navigation', async ({ page }) => {
    // Check navigation elements
    await expect(page.getByRole('link', { name: /dashboard/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /templates/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /ranges/i })).toBeVisible();
  });

  test('should display statistics cards', async ({ page }) => {
    // Dashboard should show some stats or welcome message
    const content = await page.textContent('body');
    expect(
      content?.match(/ranges|templates|vms|welcome|dashboard/i)
    ).toBeTruthy();
  });

  test('should navigate to templates page', async ({ page }) => {
    await page.getByRole('link', { name: /templates/i }).click();
    await expect(page).toHaveURL(/templates/);
  });

  test('should navigate to ranges page', async ({ page }) => {
    await page.getByRole('link', { name: /ranges/i }).click();
    await expect(page).toHaveURL(/ranges/);
  });
});
