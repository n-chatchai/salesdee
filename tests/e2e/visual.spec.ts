import { test, expect, loginWithTestUser } from './conftest';

test.describe('Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    await loginWithTestUser(page);
  });

  test('dashboard matches baseline', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveScreenshot('dashboard.png', { fullPage: true });
  });

  test('leads page matches baseline', async ({ page }) => {
    await page.goto('/crm/leads/');
    await expect(page).toHaveScreenshot('leads.png', { fullPage: true });
  });

  test('customers page matches baseline', async ({ page }) => {
    await page.goto('/crm/customers/');
    await expect(page).toHaveScreenshot('customers.png', { fullPage: true });
  });

  test('products page matches baseline', async ({ page }) => {
    await page.goto('/catalog/products/');
    await expect(page).toHaveScreenshot('products.png', { fullPage: true });
  });

  test('quotes page matches baseline', async ({ page }) => {
    await page.goto('/quotes/');
    await expect(page).toHaveScreenshot('quotes.png', { fullPage: true });
  });

  test('settings hub matches baseline', async ({ page }) => {
    await page.goto('/settings/');
    await expect(page).toHaveScreenshot('settings-hub.png', { fullPage: true });
  });
});