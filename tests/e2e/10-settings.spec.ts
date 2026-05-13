import { test, expect, loginWithTestUser } from './conftest';

test.describe('E2E: Settings & Config', () => {
  test.beforeEach(async ({ page }) => {
    await loginWithTestUser(page);
  });

  test('settings hub page loads', async ({ page }) => {
    await page.goto('/settings/');
    await expect(page.locator('body')).toBeVisible({ timeout: 15000 });
  });

  test('company settings page loads', async ({ page }) => {
    await page.goto('/settings/company/');
    await expect(page.locator('body')).toBeVisible({ timeout: 15000 });
  });

  test('pipeline settings page loads', async ({ page }) => {
    await page.goto('/settings/pipeline/');
    await expect(page.locator('body')).toBeVisible({ timeout: 15000 });
  });

  test('numbering settings page loads', async ({ page }) => {
    await page.goto('/settings/numbering/');
    await expect(page.locator('body')).toBeVisible({ timeout: 15000 });
  });

  test('members settings page loads', async ({ page }) => {
    await page.goto('/settings/members/');
    await expect(page.locator('body')).toBeVisible({ timeout: 15000 });
  });

  test('LINE settings page loads', async ({ page }) => {
    await page.goto('/settings/line/');
    await expect(page.locator('body')).toBeVisible({ timeout: 15000 });
  });
});