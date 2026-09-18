import { expect, type Page } from '@playwright/test';
import { LOCATORS, LocatorResolver } from '../core/locator-chain';
import { getSkuParam } from '../core/run-params';
import { emitParamTrace } from '../core/param-trace';
import { emitProductSearchTrace } from '../core/product-search-trace';

function normalizeSku(value: string): string {
  return value.trim().toUpperCase();
}

export class ProductSearchPage {
  private readonly resolver: LocatorResolver;

  constructor(private readonly page: Page) {
    this.resolver = new LocatorResolver(page);
  }

  async expectLoaded(): Promise<void> {
    await this.expectPageReady();
  }

  async expectPageReady(): Promise<void> {
    await this.resolver.firstVisible([...LOCATORS.productSearch.sku], 'P6_SKU', 20_000);
    await expect(this.page.locator('.t-Body-content').first()).toBeVisible();
    emitProductSearchTrace('page_ready');
  }

  private skuInput() {
    return this.page.locator('#P6_SKU, input[name="P6_SKU"]').first();
  }

  private itemIdentityInput() {
    return this.page.locator('#P6_ITEM, input[name="P6_ITEM"]').first();
  }

  async fillSku(code: string): Promise<void> {
    const input = await this.resolver.firstVisible([...LOCATORS.productSearch.sku], 'P6_SKU', 20_000);
    const selector = (await input.evaluate((el) => el.id || el.getAttribute('name') || 'sku-input')) as string;
    emitParamTrace({
      test_parameter: code,
      input_selector: selector,
      input_value: code,
    });
    await input.fill(code);
    await expect(input).toHaveValue(code);
    const filled = await input.inputValue();
    emitParamTrace({ input_value: filled });
    emitProductSearchTrace('sku_filled', filled);
  }

  async clickSearchButton(): Promise<void> {
    const search = await this.resolver.firstVisible([...LOCATORS.productSearch.search], 'search button', 10_000);
    emitParamTrace({ search_action: 'click_search_button' });
    await search.click();
    emitProductSearchTrace('search_clicked');
  }

  async waitForSearchResult(expectedSku: string): Promise<void> {
    emitProductSearchTrace('result_wait_started');
    const want = normalizeSku(expectedSku);
    const skuField = this.skuInput();
    const identity = this.itemIdentityInput();
    const resultRegion = this.page.locator(LOCATORS.productSearch.resultRegion.join(', ')).first();

    await expect(async () => {
      const inputVal = normalizeSku((await skuField.inputValue().catch(() => '')) || '');
      expect(inputVal).toBe(want);

      const hiddenVal = normalizeSku((await identity.inputValue().catch(() => '')) || '');
      const visibleMatch = await this.page.getByText(expectedSku, { exact: false }).first().isVisible().catch(() => false);
      const stockVisible = await this.page
        .locator(LOCATORS.productSearch.stockStatus.join(', '))
        .first()
        .isVisible()
        .catch(() => false);

      const identityMatches =
        hiddenVal.length > 0 &&
        (hiddenVal === want || hiddenVal.includes(want) || want.includes(hiddenVal));
      const populatedResult =
        identityMatches ||
        visibleMatch ||
        (stockVisible && (await resultRegion.isVisible().catch(() => false)));

      expect(populatedResult).toBeTruthy();
    }).toPass({ timeout: 45_000 });

    await expect(resultRegion).toBeVisible();
    emitProductSearchTrace('result_visible');
  }

  async assertResultIdentity(expectedSku: string): Promise<string> {
    const want = normalizeSku(expectedSku);
    const identity = this.itemIdentityInput();
    const hiddenVal = normalizeSku((await identity.inputValue().catch(() => '')) || '');

    if (hiddenVal.length > 0) {
      expect(hiddenVal === want || hiddenVal.includes(want) || want.includes(hiddenVal)).toBeTruthy();
      emitProductSearchTrace('result_identity', hiddenVal);
      emitProductSearchTrace('result_verified');
      return hiddenVal;
    }

    const visible = this.page.getByText(expectedSku, { exact: false }).first();
    await expect(visible).toBeVisible();
    const text = ((await visible.textContent()) || expectedSku).trim();
    emitProductSearchTrace('result_identity', text.slice(0, 120));
    emitProductSearchTrace('result_verified');
    return text;
  }

  /** End-to-end search: fill → assert input → click → wait for populated result → verify identity. */
  async searchAndVerifyProduct(itemCode?: string): Promise<string> {
    const code = itemCode ?? getSkuParam() ?? process.env.EA_VALID_ITEM_CODE;
    if (!code) {
      throw new Error('No item code — set QA_PARAM_SKU or EA_VALID_ITEM_CODE');
    }
    await this.fillSku(code);
    await this.clickSearchButton();
    await this.waitForSearchResult(code);
    const identity = await this.assertResultIdentity(code);
    emitParamTrace({ result_url: this.page.url() });
    return identity;
  }

  async searchItemCode(itemCode?: string): Promise<void> {
    await this.searchAndVerifyProduct(itemCode);
  }

  async expectResultRegion(expectedSku?: string): Promise<void> {
    const code = expectedSku ?? getSkuParam() ?? process.env.EA_VALID_ITEM_CODE;
    if (code) {
      await this.waitForSearchResult(code);
      await this.assertResultIdentity(code);
      return;
    }
    await this.page.locator('.t-Body-content, .t-Region, .a-IRR-table').first().waitFor({ state: 'visible' });
  }
}
