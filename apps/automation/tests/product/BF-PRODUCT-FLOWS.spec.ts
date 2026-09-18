import { test, expect } from '../../src/fixtures/test-base';
import { appPath } from '../../src/core/app-url';
import { attachEvidence } from '../../src/core/evidence';
import { emitParamTrace } from '../../src/core/param-trace';
import { getSkuParam } from '../../src/core/run-params';

test.describe('BF-BEST-DEAL-008 Best Deal @BF-BEST-DEAL-008 @regression @product-browse', () => {
  test('TC-BF-BEST-DEAL-008-P01 product discount page loads @sanity', async ({ page }) => {
    await page.goto(appPath('product-discount'));
    await expect(page.locator('#P92_DISCOUNT, .t-Body-content')).toBeTruthy();
  });
});

test.describe('BF-PRODUCT-CATALOGUE-006 Product Catalogue @BF-PRODUCT-CATALOGUE-006 @regression', () => {
  test('TC-BF-PRODUCT-CATALOGUE-006-P01 catalogue page loads @sanity', async ({ page }) => {
    await page.goto(appPath('product-catalogue'));
    await expect(page.locator('body')).toBeVisible();
  });
});

test.describe('BF-PRODUCT-004 View Product @BF-PRODUCT-004 @regression @product-management', () => {
  test('TC-BF-PRODUCT-004-P01 product detail reachable from search @sanity @positive', async ({
    authenticatedPage,
    productSearchPage,
    page,
  }, testInfo) => {
    const requestSku = getSkuParam();
    emitParamTrace({
      request_sku: requestSku,
      validated_sku: requestSku,
      suite_parameter: requestSku,
      test_parameter: requestSku,
    });

    await authenticatedPage.openItemSearch();
    await productSearchPage.expectPageReady();

    const sku = requestSku || process.env.EA_VALID_ITEM_CODE;
    test.skip(!sku, 'QA_PARAM_SKU or EA_VALID_ITEM_CODE required');

    await productSearchPage.searchAndVerifyProduct(sku!);
    await productSearchPage.openProductDetailFromSearchResult(sku!);
    await productSearchPage.expectProductDetailForSku(sku!);
    await attachEvidence(page, testInfo, 'product-detail-visible');
  });
});

test.describe('BF-PRODUCT-003 Search Product @BF-PRODUCT-003 @regression @product-search', () => {
  test('TC-BF-PRODUCT-003-P01 direct product search page @sanity @positive', async ({
    authenticatedPage,
    productSearchPage,
    page,
  }, testInfo) => {
    const requestSku = getSkuParam();
    emitParamTrace({
      request_sku: requestSku,
      validated_sku: requestSku,
      suite_parameter: requestSku,
      test_parameter: requestSku,
    });

    await authenticatedPage.openItemSearch();
    await productSearchPage.expectPageReady();

    if (requestSku) {
      await productSearchPage.searchAndVerifyProduct(requestSku);
      await expect(page.locator('#P6_SKU, input[name="P6_SKU"]').first()).toHaveValue(requestSku);
      await attachEvidence(page, testInfo, 'product-search-result-visible');
      return;
    }

    const fallback = process.env.EA_VALID_ITEM_CODE;
    test.skip(!fallback, 'QA_PARAM_SKU or EA_VALID_ITEM_CODE required');
    await productSearchPage.searchAndVerifyProduct(fallback!);
    await attachEvidence(page, testInfo, 'product-search-result-visible');
  });
});
