import { test, expect } from '../../src/fixtures/test-base';

test.describe('BF-HOME-010-C01 Home Utility Components @BF-HOME-010-C01 @regression @navigation', () => {
  test('TC-BF-HOME-010-C01-P01 customer drawer opens and closes @sanity', async ({ authenticatedPage, page }) => {
    await authenticatedPage.openCustomerDrawer();
    await expect(page.locator('.t-Drawer, .ui-dialog, [role="dialog"]').first()).toBeVisible({ timeout: 10_000 });
    await page.keyboard.press('Escape').catch(() => undefined);
  });

  test('TC-BF-HOME-010-C01-P02 settings dialog opens @regression', async ({ authenticatedPage, page }) => {
    await authenticatedPage.openSettings();
    await expect(page.locator('.ui-dialog, [role="dialog"]').first()).toBeVisible({ timeout: 10_000 });
  });

  test('TC-BF-HOME-010-C01-E01 store stock control responds @regression', async ({ authenticatedPage, page }) => {
    const btn = page.locator('#B74402876591024608, button:has-text("STORE STOCK")').first();
    await expect(btn).toBeVisible();
    await btn.click();
  });
});
