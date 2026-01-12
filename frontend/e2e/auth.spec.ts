import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display login page by default', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /login/i })).toBeVisible();
    await expect(page.getByPlaceholder(/email/i)).toBeVisible();
    await expect(page.getByPlaceholder(/password/i)).toBeVisible();
  });

  test('should show error with invalid credentials', async ({ page }) => {
    await page.getByPlaceholder(/email/i).fill('invalid@test.com');
    await page.getByPlaceholder(/password/i).fill('wrongpassword');
    await page.getByRole('button', { name: /login/i }).click();

    await expect(page.getByText(/invalid|error|failed/i)).toBeVisible();
  });

  test('should navigate to register page', async ({ page }) => {
    await page.getByRole('link', { name: /register|sign up/i }).click();
    await expect(page.getByRole('heading', { name: /register|sign up/i })).toBeVisible();
  });

  test('should register a new user', async ({ page }) => {
    await page.getByRole('link', { name: /register|sign up/i }).click();

    const uniqueEmail = `test-${Date.now()}@example.com`;
    await page.getByPlaceholder(/username/i).fill(`testuser_${Date.now()}`);
    await page.getByPlaceholder(/email/i).fill(uniqueEmail);
    await page.getByPlaceholder(/password/i).first().fill('TestPassword123!');

    // If there's a confirm password field
    const confirmPassword = page.getByPlaceholder(/confirm/i);
    if (await confirmPassword.isVisible()) {
      await confirmPassword.fill('TestPassword123!');
    }

    await page.getByRole('button', { name: /register|sign up/i }).click();

    // Should redirect to login or dashboard after registration
    await expect(page).toHaveURL(/login|dashboard/);
  });

  test('should login with valid credentials', async ({ page }) => {
    // First register a user
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

    // Wait for registration to complete
    await page.waitForURL(/login|dashboard/);

    // If redirected to login, login with the credentials
    if (page.url().includes('login')) {
      await page.getByPlaceholder(/email/i).fill(email);
      await page.getByPlaceholder(/password/i).fill(password);
      await page.getByRole('button', { name: /login/i }).click();
    }

    // Should be on dashboard
    await expect(page).toHaveURL(/dashboard/);
  });

  test('should logout successfully', async ({ page }) => {
    // Login first
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

    // Find and click logout
    await page.getByRole('button', { name: /logout|sign out/i }).click();

    // Should be back on login page
    await expect(page).toHaveURL(/login/);
  });
});
