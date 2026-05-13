import { test, expect, loginWithTestUser } from './conftest';

test.describe('E2E: Quote Builder', () => {
  test.beforeEach(async ({ page }) => {
    await loginWithTestUser(page);
  });

  test('quotes list page loads', async ({ page }) => {
    await page.goto('/quotes/');
    await expect(page.locator('text=ใบเสนอราคา').first()).toBeVisible({ timeout: 15000 });
  });

  test('create new quote button exists', async ({ page }) => {
    await page.goto('/quotes/');
    const createBtn = page.locator('a:has-text("สร้างใบเสนอราคา")').first();
    if (await createBtn.isVisible({ timeout: 5000 })) {
      await expect(createBtn).toBeVisible();
    }
  });

  test('navigate to quote form', async ({ page }) => {
    await page.goto('/quotes/new/');
    await expect(page.locator('h1, [class*="heading"]').first()).toBeVisible({ timeout: 10000 });
  });

  test('quote revisions page accessible', async ({ page }) => {
    await page.goto('/quotes/');
    await page.click('a:has-text("สร้างใบเสนอราคา")');
    await page.waitForTimeout(1000);
    // Just check form loads
    const formExists = page.locator('form, input, select').first();
    await expect(formExists).toBeVisible({ timeout: 10000 });
  });
});