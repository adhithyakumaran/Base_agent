import type { Page } from '@playwright/test';
import { LOCATORS, LocatorResolver } from '../core/locator-chain';
import { getSkuParam } from '../core/run-params';
import { emitParamTrace } from '../core/param-trace';

export class ProductSearchPage {
  private readonly resolver: LocatorResolver;

  constructor(private readonly page: Page) {
    this.resolver = new LocatorResolver(page);
  }

  async expectLoaded(): Promise<void> {
    await this.resolver.firstVisible([...LOCATORS.productSearch.sku], 'P6_SKU', 20_000);
  }

  async searchItemCode(itemCode?: string): Promise<void> {
    const code = itemCode ?? getSkuParam() ?? process.env.EA_VALID_ITEM_CODE;
    if (!code) {
      throw new Error('No item code — set QA_PARAM_SKU or EA_VALID_ITEM_CODE');
    }
    const input = await this.resolver.firstVisible([...LOCATORS.productSearch.sku], 'P6_SKU', 20_000);
    const search = await this.resolver.firstVisible([...LOCATORS.productSearch.search], 'search button', 10_000);
    const selector = (await input.evaluate((el) => el.id || el.getAttribute('name') || 'sku-input')) as string;
    emitParamTrace({
      test_parameter: code,
      input_selector: selector,
      input_value: code,
      search_action: 'click_search_button',
    });
    await input.fill(code);
    const filled = await input.inputValue();
    emitParamTrace({ input_value: filled });
    await Promise.all([
      this.page.waitForLoadState('domcontentloaded').catch(() => undefined),
      search.click(),
    ]);
    emitParamTrace({ result_url: this.page.url() });
  }

  async expectResultRegion(): Promise<void> {
    await this.page.locator('.t-Body-content, .t-Region, .a-IRR-table').first().waitFor({ state: 'visible' });
  }
}
