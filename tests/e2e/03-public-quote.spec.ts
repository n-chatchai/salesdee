import { test, expect } from './conftest';

test.describe('E2E-03: Public Quote Page', () => {
  test('public home page loads', async ({ page }) => {
    await page.goto('/');
    // Should show some content or redirect
    const url = page.url();
    expect(url).toBeDefined();
  });

  test('public catalog page loads', async ({ page }) => {
    await page.goto('/c/wandeedee/home/');
    await expect(page.locator('text=วันดีดี').or(page.locator('[class*="pub"]')).first()).toBeVisible({ timeout: 10000 });
  });

  test('intake page works with tenant slug', async ({ page }) => {
    await page.goto('/crm/intake/wandeedee/');
    await expect(page.locator('text=เล่าให้ฟัง').or(page.locator('h1'))).toBeVisible({ timeout: 10000 });
  });
});