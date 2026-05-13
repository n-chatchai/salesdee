import { test, expect, loginWithTestUser } from './conftest';

test.describe('E2E: Additional Integrations', () => {
  test.beforeEach(async ({ page }) => {
    await loginWithTestUser(page);
  });

  test('inbox page loads', async ({ page }) => {
    await page.goto('/integrations/inbox/');
    await expect(page.locator('body')).toBeVisible({ timeout: 15000 });
  });

  test('public catalog accessible', async ({ page }) => {
    await page.goto('/c/wandeedee/');
    await expect(page.locator('body')).toBeVisible({ timeout: 15000 });
  });

  test('public product page accessible', async ({ page }) => {
    // Go to products first
    await page.goto('/catalog/products/');
    // Find product link
    const productLink = page.locator('a[href*="/products/"]').first();
    if (await productLink.isVisible({ timeout: 5000 })) {
      await productLink.click();
      await expect(page.locator('text=รายละเอียด').or(page.locator('h1'))).toBeVisible({ timeout: 10000 });
    }
  });

  test('search functionality works', async ({ page }) => {
    await page.goto('/crm/customers/');
    // Find search input
    const searchInput = page.locator('input[type="search"], input[name="q"]').first();
    if (await searchInput.isVisible({ timeout: 5000 })) {
      await searchInput.fill('test');
      await searchInput.press('Enter');
      await page.waitForTimeout(1000);
      // Should show results or empty state
      expect(page.url()).toContain('q=');
    }
  });
});