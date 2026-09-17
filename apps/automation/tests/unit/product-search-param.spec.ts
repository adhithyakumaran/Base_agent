import { test, expect } from '@playwright/test';
import { ProductSearchPage } from '../../src/pages/product-search.page';

test.use({ video: 'off', trace: 'off' });

test.describe('ProductSearchPage parameterized SKU', () => {
  test('searchItemCode fills QA_PARAM_SKU into the search field', async ({ page }) => {
    const expectedSku = '552811DUDABA00';
    process.env.QA_PARAM_SKU = expectedSku;

    await page.setContent(`
      <html><body>
        <input id="P6_SKU" name="P6_SKU" placeholder="Enter item code or scan the QR" />
        <button id="btn_search" title="Search" aria-label="Search">Search</button>
      </body></html>
    `);

    const productSearch = new ProductSearchPage(page);
    await productSearch.searchItemCode();
    await expect(page.locator('#P6_SKU')).toHaveValue(expectedSku);

    delete process.env.QA_PARAM_SKU;
  });
});
