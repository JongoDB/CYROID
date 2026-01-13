import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display login page by default', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible();
    await expect(page.getByRole('textbox', { name: /username/i })).toBeVisible();
    await expect(page.getByRole('textbox', { name: /password/i })).toBeVisible();
  });

  test('should show error with invalid credentials', async ({ page }) => {
    await page.getByRole('textbox', { name: /username/i }).fill('invaliduser');
    await page.getByRole('textbox', { name: /password/i }).fill('wrongpassword');
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page.getByText(/invalid|error|failed|incorrect/i)).toBeVisible();
  });

  test('should navigate to register page', async ({ page }) => {
    await page.getByRole('link', { name: /create a new account/i }).click();
    await expect(page.getByRole('heading', { name: /create.*account|register|sign up/i })).toBeVisible();
  });

  test('should register a new user', async ({ page }) => {
    await page.getByRole('link', { name: /create a new account/i }).click();

    const uniqueId = Date.now();
    await page.getByRole('textbox', { name: /username/i }).fill(`testuser_${uniqueId}`);
    await page.getByRole('textbox', { name: /email/i }).fill(`test-${uniqueId}@example.com`);
    await page.getByRole('textbox', { name: /^password$/i }).fill('TestPassword123!');
    await page.getByRole('textbox', { name: /confirm password/i }).fill('TestPassword123!');

    await page.getByRole('button', { name: /create account|register|sign up/i }).click();

    // Should redirect to login after registration
    await expect(page).toHaveURL(/login/, { timeout: 10000 });
  });

  test('should login with valid credentials', async ({ page }) => {
    // First register a user
    await page.getByRole('link', { name: /create a new account/i }).click();

    const uniqueId = Date.now();
    const username = `testuser_${uniqueId}`;
    const email = `test-${uniqueId}@example.com`;
    const password = 'TestPassword123!';

    await page.getByRole('textbox', { name: /username/i }).fill(username);
    await page.getByRole('textbox', { name: /email/i }).fill(email);
    await page.getByRole('textbox', { name: /^password$/i }).fill(password);
    await page.getByRole('textbox', { name: /confirm password/i }).fill(password);

    await page.getByRole('button', { name: /create account|register|sign up/i }).click();

    // Wait for registration to complete and redirect to login
    await page.waitForURL(/login/, { timeout: 10000 });

    // Login with the credentials
    await page.getByRole('textbox', { name: /username/i }).fill(username);
    await page.getByRole('textbox', { name: /password/i }).fill(password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Should be on dashboard (root path)
    await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible({ timeout: 10000 });
  });

  test('should logout successfully', async ({ page }) => {
    // Register and login first
    await page.getByRole('link', { name: /create a new account/i }).click();

    const uniqueId = Date.now();
    const username = `testuser_${uniqueId}`;
    const email = `test-${uniqueId}@example.com`;
    const password = 'TestPassword123!';

    await page.getByRole('textbox', { name: /username/i }).fill(username);
    await page.getByRole('textbox', { name: /email/i }).fill(email);
    await page.getByRole('textbox', { name: /^password$/i }).fill(password);
    await page.getByRole('textbox', { name: /confirm password/i }).fill(password);

    await page.getByRole('button', { name: /create account|register|sign up/i }).click();
    await page.waitForURL(/login/, { timeout: 10000 });

    await page.getByRole('textbox', { name: /username/i }).fill(username);
    await page.getByRole('textbox', { name: /password/i }).fill(password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Should be on dashboard (root path)
    await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible({ timeout: 10000 });

    // Find and click logout
    await page.getByRole('button', { name: /logout|sign out/i }).click();

    // Should be back on login page
    await expect(page).toHaveURL(/login/);
  });
});
