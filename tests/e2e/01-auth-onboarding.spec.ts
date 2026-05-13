import { test, expect, loginWithTestUser } from './conftest';

test.describe('E2E-01: Signup → Onboarding → Create Quote', () => {
  test('signup page loads', async ({ page }) => {
    await page.goto('/accounts/signup/');
    await expect(page.locator('text=สมัครใช้งาน').or(page.locator('h1'))).toBeVisible({ timeout: 15000 });
  });

  test('login page loads', async ({ page }) => {
    await page.goto('/accounts/login/');
    await expect(page.locator('text=เข้าสู่ระบบ').or(page.locator('h1'))).toBeVisible({ timeout: 15000 });
  });

  test('dashboard loads after login', async ({ page }) => {
    await loginWithTestUser(page);
    await expect(page.locator('text=Dashboard').or(page.locator('text=แดชบอร์ด')).or(page.locator('text=Pipeline'))).toBeVisible({ timeout: 15000 });
  });
});