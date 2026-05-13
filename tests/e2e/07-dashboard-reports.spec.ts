import { test, expect, loginWithTestUser } from './conftest';

test.describe('P1: Dashboard & Reports', () => {
  test.beforeEach(async ({ page }) => {
    await loginWithTestUser(page);
  });

  test('dashboard loads', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('text=หน้าหลัก').or(page.locator('h1'))).toBeVisible({ timeout: 15000 });
  });

  test('leads page accessible', async ({ page }) => {
    await page.goto('/crm/leads/');
    await expect(page.locator('text=Lead').or(page.locator('text=ลูกค้าเป้าหมาย')).first()).toBeVisible({ timeout: 15000 });
  });

  test('tasks page accessible', async ({ page }) => {
    await page.goto('/crm/tasks/');
    await expect(page.locator('text=งาน').or(page.locator('text=Task')).first()).toBeVisible({ timeout: 15000 });
  });
});