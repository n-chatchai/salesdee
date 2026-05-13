import { test, expect, loginWithTestUser } from './conftest';

test.describe('E2E-02: Lead → Deal → Quote → Send', () => {
  test.beforeEach(async ({ page }) => {
    await loginWithTestUser(page);
  });

  test('leads page loads', async ({ page }) => {
    await page.goto('/crm/leads/');
    await expect(page.locator('text=ลีดใหม่').or(page.locator('text=Lead')).first()).toBeVisible({ timeout: 15000 });
  });

  test('pipeline page loads', async ({ page }) => {
    await page.goto('/crm/');
    await expect(page.locator('text=ดีลใหม่').or(page.locator('text=Pipeline')).first()).toBeVisible({ timeout: 15000 });
  });

  test('navigate to create lead', async ({ page }) => {
    await page.goto('/crm/leads/');
    await page.click('a:has-text("ลีดใหม่")');
    await expect(page.locator('text=ลีดใหม่').or(page.locator('h1'))).toBeVisible({ timeout: 10000 });
  });

  test('quotes list accessible', async ({ page }) => {
    await page.goto('/quotes/');
    await expect(page.locator('text=ใบเสนอราคา').first()).toBeVisible({ timeout: 15000 });
  });

  test('navigate to create deal', async ({ page }) => {
    await page.goto('/crm/');
    await page.click('a:has-text("ดีลใหม่")');
    await expect(page.locator('text=ดีลใหม่').or(page.locator('h1'))).toBeVisible({ timeout: 10000 });
  });
});