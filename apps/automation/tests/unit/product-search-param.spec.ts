import { test, expect } from '@playwright/test';
import { ProductSearchPage } from '../../src/pages/product-search.page';

test.use({ video: 'off', trace: 'off' });

const MOCK_PAGE = `
  <html><body>
    <div class="t-Body-content">
      <input id="P6_SKU" name="P6_SKU" placeholder="Enter item code or scan the QR" />
      <input id="P6_ITEM" name="P6_ITEM" type="hidden" value="" />
      <button id="btn_search" title="Search" aria-label="Search">Search</button>
      <div id="result-panel" class="t-Region-body" style="display:none">
        <span id="result-label"></span>
        <span class="stock">Sold Out</span>
      </div>
    </div>
    <script>
      document.getElementById('btn_search').addEventListener('click', () => {
        const sku = document.getElementById('P6_SKU').value;
        document.getElementById('P6_ITEM').value = sku.toUpperCase();
        const panel = document.getElementById('result-panel');
        panel.style.display = 'block';
        document.getElementById('result-label').textContent = sku;
      });
    </script>
  </body></html>
`;

test.describe('ProductSearchPage parameterized SKU', () => {
  test('searchAndVerifyProduct fills SKU, clicks search, waits for visible result', async ({ page }) => {
    const expectedSku = '552811DUDABA00';
    process.env.QA_PARAM_SKU = expectedSku;
    await page.setContent(MOCK_PAGE);

    const productSearch = new ProductSearchPage(page);
    await productSearch.expectPageReady();
    const identity = await productSearch.searchAndVerifyProduct();
    expect(identity).toBe(expectedSku.toUpperCase());
    await expect(page.locator('#P6_SKU')).toHaveValue(expectedSku);
    await expect(page.locator('#P6_ITEM')).toHaveValue(expectedSku.toUpperCase());
    await expect(page.locator('#result-panel')).toBeVisible();
    await expect(page.getByText(expectedSku)).toBeVisible();

    delete process.env.QA_PARAM_SKU;
  });

  test('searchItemCode fills QA_PARAM_SKU into the search field', async ({ page }) => {
    const expectedSku = '552811DUDABA00';
    process.env.QA_PARAM_SKU = expectedSku;
    await page.setContent(MOCK_PAGE);

    const productSearch = new ProductSearchPage(page);
    await productSearch.searchItemCode();
    await expect(page.locator('#P6_SKU')).toHaveValue(expectedSku);
    await expect(page.locator('#result-panel')).toBeVisible();

    delete process.env.QA_PARAM_SKU;
  });
});
