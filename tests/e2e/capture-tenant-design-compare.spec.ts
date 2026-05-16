/**
 * One-shot capture: design deck frames vs implemented tenant-site pages.
 * Run: npx playwright test capture-tenant-design-compare --project=chromium
 * Output: design/compare/screenshots/
 */
import { test } from '@playwright/test';
import path from 'path';
import fs from 'fs';

const OUT = path.join(process.cwd(), 'design', 'compare', 'screenshots');
const SLUG = 'wandeedee';
const DESIGN_FILE = path.join(process.cwd(), 'design', 'tenant-site.html');

const FRAMES: { id: string; label: string; appPath?: string }[] = [
  { id: 'home', label: 'a · landing', appPath: `/c/${SLUG}/home/` },
  { id: 'category', label: 'b · catalog', appPath: `/c/${SLUG}/` },
  { id: 'product', label: 'c · product', appPath: `__PRODUCT__` },
  { id: 'checkout', label: 'e · quote request', appPath: `/c/${SLUG}/request/` },
  { id: 'success', label: 'f · thanks', appPath: undefined },
  { id: 'search', label: 'h · search', appPath: `/c/${SLUG}/search/?q=โต๊ะ` },
  { id: 'compare', label: 'i · compare', appPath: `/c/${SLUG}/compare/` },
  { id: 'bulk', label: 'j · bulk', appPath: `/c/${SLUG}/bulk/` },
  { id: 'showroom', label: 'k · showroom', appPath: `/c/${SLUG}/showroom/` },
];

test.describe.configure({ mode: 'serial' });

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
});

test('capture design deck frames', async ({ page }) => {
  const designUrl = `file://${DESIGN_FILE}`;
  await page.goto(designUrl, { waitUntil: 'networkidle', timeout: 120000 });
  await page.setViewportSize({ width: 1440, height: 900 });

  for (const f of FRAMES) {
    const section = page.locator(`#${f.id}.frame-wrapper`);
    if ((await section.count()) === 0) continue;
    await section.scrollIntoViewIfNeeded();
    await page.waitForTimeout(400);
    const frame = section.locator('.frame').first();
    await frame.screenshot({
      path: path.join(OUT, `design-${f.id}.png`),
      animations: 'disabled',
    });
  }
});

test('capture implemented tenant pages', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });

  let productPath = `/c/${SLUG}/`;
  await page.goto(productPath, { waitUntil: 'networkidle', timeout: 60000 });
  const productLink = page.locator(`a[href*="/c/${SLUG}/p/"]`).first();
  if (await productLink.count()) {
    productPath = (await productLink.getAttribute('href')) || productPath;
  }

  for (const f of FRAMES) {
    if (!f.appPath) continue;
    const url = f.appPath === '__PRODUCT__' ? productPath : f.appPath;
    const resp = await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    if (!resp || resp.status() >= 400) {
      await page.screenshot({
        path: path.join(OUT, `app-${f.id}-ERROR.png`),
        fullPage: true,
      });
      continue;
    }
    await page.waitForTimeout(500);
    await page.screenshot({
      path: path.join(OUT, `app-${f.id}.png`),
      fullPage: true,
      animations: 'disabled',
    });
    await page.pdf({
      path: path.join(OUT, `app-${f.id}.pdf`),
      format: 'A4',
      printBackground: true,
    });
  }
});
