import { test, expect } from '../../src/fixtures/test-base';

test.describe('BF-BEST-DEAL-008 Best Deal @BF-BEST-DEAL-008 @regression @product-browse', () => {
  test('TC-BF-BEST-DEAL-008-P01 product discount page loads @sanity', async ({ page }) => {
    await page.goto('/product-discount');
    await expect(page.locator('#P92_DISCOUNT, .t-Body-content')).toBeTruthy();
  });
});

test.describe('BF-PRODUCT-CATALOGUE-006 Product Catalogue @BF-PRODUCT-CATALOGUE-006 @regression', () => {
  test('TC-BF-PRODUCT-CATALOGUE-006-P01 catalogue page loads @sanity', async ({ page }) => {
    await page.goto('/product-catalogue');
    await expect(page.locator('body')).toBeVisible();
  });
});

test.describe('BF-PRODUCT-004 View Product @BF-PRODUCT-004 @regression @product-management', () => {
  test('TC-BF-PRODUCT-004-P01 product detail reachable from search @sanity', async ({
    authenticatedPage,
    productSearchPage,
    page,
  }) => {
    const item = process.env.EA_VALID_ITEM_CODE;
    test.skip(!item, 'EA_VALID_ITEM_CODE not configured');
    await authenticatedPage.openItemSearch();
    await productSearchPage.searchItemCode(item!);
    await expect(page.locator('.t-Body-content')).toBeVisible();
  });
});

test.describe('BF-PRODUCT-003 Search Product @BF-PRODUCT-003 @regression @product-search', () => {
  test('TC-BF-PRODUCT-003-P01 direct product search page @sanity', async ({ page }) => {
    await page.goto('/product-detail-item-search');
    await expect(page.locator('#P6_SKU')).toBeVisible();
  });
});
