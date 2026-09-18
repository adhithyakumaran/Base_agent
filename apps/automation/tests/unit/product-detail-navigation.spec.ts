import { expect, test } from '@playwright/test';
import { ProductSearchPage } from '../../src/pages/product-search.page';

test.describe('Product detail navigation @unit', () => {
  test('openProductDetailFromSearchResult navigates to product-detail URL', async ({ page }) => {
    const sku = '552811DUDABA00';
    await page.route('**/*', async (route) => {
      const url = route.request().url();
      if (url.includes('product-detail-item-search')) {
        await route.fulfill({
          status: 200,
          contentType: 'text/html',
          body: `<div class="t-Body-content"><a href="/ords/r/tjdcom/ea/product-detail?item=1">View Product</a></div>`,
        });
        return;
      }
      if (url.includes('/ea/product-detail')) {
        await route.fulfill({
          status: 200,
          contentType: 'text/html',
          body: `<div class="t-Body-content"><span>${sku}</span><img src="/p.jpg" /><span>Price</span><span>In Stock</span></div>`,
        });
        return;
      }
      await route.continue();
    });

    await page.goto('https://example.com/ords/r/tjdcom/ea/product-detail-item-search');
    const searchPage = new ProductSearchPage(page);
    await searchPage.openProductDetailFromSearchResult(sku);
    await expect(page).toHaveURL(/product-detail/);
  });
});
