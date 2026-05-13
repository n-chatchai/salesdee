import { test, expect, loginWithTestUser } from './conftest';

test.describe('E2E: Tasks & Activities', () => {
  test.beforeEach(async ({ page }) => {
    await loginWithTestUser(page);
  });

  test('tasks page loads', async ({ page }) => {
    await page.goto('/crm/tasks/');
    const content = page.locator('main, .content');
    await expect(content.first()).toBeVisible({ timeout: 15000 });
  });

  test('lead detail accessible', async ({ page }) => {
    await page.goto('/crm/leads/');
    const leadLink = page.locator('a[href*="/leads/"]').first();
    if (await leadLink.isVisible({ timeout: 5000 })) {
      await leadLink.click();
      await page.waitForTimeout(1000);
    }
  });
});