import { test, expect } from './conftest';

test.describe('Visual Regression - Public Pages', () => {
  test('public home matches baseline', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveScreenshot('public-home.png', { fullPage: true });
  });

  test('public catalog matches baseline', async ({ page }) => {
    await page.goto('/c/wandeedee/');
    await expect(page).toHaveScreenshot('public-catalog.png', { fullPage: true });
  });

  test('login page matches baseline', async ({ page }) => {
    await page.goto('/accounts/login/');
    await expect(page).toHaveScreenshot('login.png', { fullPage: true });
  });

  test('signup page matches baseline', async ({ page }) => {
    await page.goto('/accounts/signup/');
    await expect(page).toHaveScreenshot('signup.png', { fullPage: true });
  });
});