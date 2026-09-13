import { test, expect } from '../../src/fixtures/test-base';
import { ProductSearchPage } from '../../src/pages/product-search.page';

test.describe('QA_PARAM_SKU parameterized execution @BF-PRODUCT-003 @positive @param-test', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test('TC-PARAM-SKU-001 QA_PARAM_SKU reaches browser input', async ({ page }) => {
    const expectedSku = process.env.QA_PARAM_SKU;
    test.skip(!expectedSku, 'QA_PARAM_SKU not set');

    await page.setContent(`
      <html><body>
        <input id="P6_SKU" name="P6_SKU" placeholder="Enter item code or scan the QR" />
        <button id="btn_search" title="Search" aria-label="Search">Search</button>
      </body></html>
    `);

    const productSearch = new ProductSearchPage(page);
    await productSearch.searchItemCode();

    await expect(page.locator('#P6_SKU')).toHaveValue(expectedSku!);
  });
});
