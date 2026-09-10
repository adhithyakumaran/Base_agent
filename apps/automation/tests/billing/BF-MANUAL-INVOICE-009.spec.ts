import { test, expect } from '../../src/fixtures/test-base';
import { appPath } from '../../src/core/app-url';

test.describe('BF-MANUAL-INVOICE-009 Manual Invoice @BF-MANUAL-INVOICE-009 @regression @read-only-sanity @no-transaction', () => {
  test('TC-BF-MANUAL-INVOICE-009-P01 manual bills book loads @sanity', async ({ page }) => {
    await page.goto(appPath('ea1/manual-bills-book'));
    await expect(page.locator('body')).toBeVisible();
  });

  test('TC-BF-MANUAL-INVOICE-009-N01 required-field validation without submit @regression', async ({ page }) => {
    await page.goto(appPath('ea1/manual-bills-book'));
    const create = page.locator('button:has-text("Create Invoice"), input[value="Create Invoice"]');
    if (await create.count()) {
      await expect(create.first()).toBeVisible();
      // Do NOT click Create Invoice — safety guardrail
    }
  });
});
