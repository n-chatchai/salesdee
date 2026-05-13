import { test as base, Page, expect } from '@playwright/test';

export const test = base.extend<{
  page: Page;
}>({
  page: async ({ page }, use) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await use(page);
  },
});

export { expect };

export async function loginAs(page: Page, email: string, password: string) {
  await page.goto('/accounts/login/');
  // Django auth form uses 'username' field
  await page.fill('input[name="username"]', email);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL('/', { timeout: 15000 });
}

export async function loginWithTestUser(page: Page) {
  // Use hardcoded test credentials
  // Run: python manage.py create_e2e_user to create this user first
  await loginAs(page, 'e2e@test.com', 'TestPass123!');
}

export async function createTestTenant(page: Page) {
  const timestamp = Date.now();
  return {
    businessName: `Test Company ${timestamp}`,
    email: `test${timestamp}@example.com`,
    password: 'TestPass123!',
  };
}

export async function createTestCustomer(page: Page, name: string = 'ลูกค้าทดสอบ') {
  await page.goto('/crm/customers/');
  await page.click('a:has-text("เพิ่มลูกค้า"), button:has-text("เพิ่ม")');
  await page.fill('[name="name"]', name);
  await page.click('button:has-text("บันทึก")');
  await page.waitForURL(/\/crm\/customers\/\d+\//);
}

export async function createTestProduct(page: Page, name: string = 'โต๊ะทดสอบ') {
  await page.goto('/catalog/products/');
  await page.click('a:has-text("เพิ่มสินค้า"), button:has-text("เพิ่ม")');
  await page.fill('[name="name"]', name);
  await page.fill('[name="unit_price"]', '5000');
  await page.click('button:has-text("บันทึก")');
  await page.waitForURL(/\/catalog\/products\/\d+\//);
}

export async function createTestLead(page: Page, name: string = 'Lead ทดสอบ') {
  await page.goto('/crm/leads/');
  await page.click('a:has-text("เพิ่ม Lead")');
  await page.fill('[name="name"]', name);
  await page.click('button:has-text("บันทึก")');
  await page.waitForURL(/\/crm\/leads\/\d+\//);
}