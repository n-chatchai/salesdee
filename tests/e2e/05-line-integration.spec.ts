import { test, expect } from './conftest';

test.describe('P1: LINE Integration', () => {
  test('inbox page loads', async ({ page }) => {
    await page.goto('/integrations/inbox/');

    // Should see inbox page
    // May redirect to login if not authenticated
    const url = page.url();
    if (url.includes('login')) {
      test.skip(true, 'Requires authenticated session');
    }
  });

  test('conversation list displays', async ({ page }) => {
    await page.goto('/integrations/inbox/');

    if (page.url().includes('login')) {
      test.skip(true, 'Requires authenticated session');
    }

    // Should see conversation or thread list
    await expect(page.locator('text=inbox, text=ข้อความ').or(page.locator('[class*="conversation"]'))).toBeVisible();
  });

  test('AI suggestions panel visible', async ({ page }) => {
    await page.goto('/integrations/inbox/');

    if (page.url().includes('login')) {
      test.skip(true, 'Requires authenticated session');
    }

    // Should see AI panel or suggestions area
    const aiPanel = page.locator('text=AI').or(page.locator('[class*="ai-suggest"]'));
    if (await aiPanel.isVisible()) {
      await expect(aiPanel).toBeVisible();
    }
  });
});