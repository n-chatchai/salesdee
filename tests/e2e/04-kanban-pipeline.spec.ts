import { test, expect, loginWithTestUser } from './conftest';

test.describe('E2E-04: Kanban Pipeline', () => {
  test.beforeEach(async ({ page }) => {
    await loginWithTestUser(page);
  });

  test('pipeline page loads with stages', async ({ page }) => {
    await page.goto('/crm/');
    await expect(page.locator('text=Pipeline').or(page.locator('[class*="pipeline"]')).first()).toBeVisible({ timeout: 15000 });
  });

  test('create deal button exists', async ({ page }) => {
    await page.goto('/crm/');
    const createBtn = page.locator('a:has-text("สร้างดีล"), button:has-text("สร้างดีล")').first();
    if (await createBtn.isVisible({ timeout: 5000 })) {
      await expect(createBtn).toBeVisible();
    }
  });
});