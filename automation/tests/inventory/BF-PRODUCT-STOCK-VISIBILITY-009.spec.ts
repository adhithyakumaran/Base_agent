import { test, expect } from '../../src/fixtures/test-base';

test.describe('BF-PRODUCT-STOCK-VISIBILITY-009 @BF-PRODUCT-STOCK-VISIBILITY-009 @regression @inventory', () => {
  test('TC-BF-PRODUCT-STOCK-VISIBILITY-009-P01 valid 14-digit code returns stock view @sanity', async ({
    authenticatedPage,
    stockVisibilityPage,
    page,
  }) => {
    const item = process.env.EA_VALID_ITEM_CODE;
    test.skip(!item, 'EA_VALID_ITEM_CODE not configured');

    await authenticatedPage.openProductStockVisibility();
    await stockVisibilityPage.expectLoaded();
    await stockVisibilityPage.searchItemCode(item!);
    await expect(page.locator('.t-Body-content')).toBeVisible();
  });

  test('TC-BF-PRODUCT-STOCK-VISIBILITY-009-N01 incomplete item code shows validation @regression', async ({
    authenticatedPage,
    stockVisibilityPage,
    page,
  }) => {
    await authenticatedPage.openProductStockVisibility();
    await stockVisibilityPage.expectLoaded();
    await stockVisibilityPage.searchItemCode('123');
    await expect(page.locator('text=/14 Digit|Item code/i')).toBeVisible({ timeout: 10_000 });
  });
});
