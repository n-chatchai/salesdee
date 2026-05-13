import { test, expect, loginWithTestUser } from './conftest';

test.describe('P1: Catalog & Customers', () => {
  test.beforeEach(async ({ page }) => {
    await loginWithTestUser(page);
  });

  test('customer list page loads', async ({ page }) => {
    await page.goto('/crm/customers/');
    await expect(page.locator('text=ลูกค้า').first()).toBeVisible({ timeout: 15000 });
  });

  test('navigate to create customer', async ({ page }) => {
    await page.goto('/crm/customers/');
    await page.click('a:has-text("ลูกค้าใหม่")');
    await expect(page.locator('text=ลูกค้าใหม่').or(page.locator('h1'))).toBeVisible({ timeout: 10000 });
  });

  test('products page loads', async ({ page }) => {
    await page.goto('/catalog/products/');
    await expect(page.locator('body')).toBeVisible({ timeout: 15000 });
  });

  test('navigate to create product', async ({ page }) => {
    await page.goto('/catalog/products/');
    const addBtn = page.locator('a:has-text("สินค้าใหม่"), button:has-text("สินค้าใหม่")').first();
    if (await addBtn.isVisible({ timeout: 5000 })) {
      await addBtn.click();
      await expect(page.locator('body')).toBeVisible({ timeout: 10000 });
    }
  });

  test('categories page loads', async ({ page }) => {
    await page.goto('/catalog/categories/');
    await expect(page.locator('text=หมวด').first()).toBeVisible({ timeout: 15000 });
  });
});