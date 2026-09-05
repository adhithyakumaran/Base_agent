import type { Page } from '@playwright/test';
import { LOCATORS, LocatorResolver } from '../core/locator-chain';

export class ProductSearchPage {
  private readonly resolver: LocatorResolver;

  constructor(private readonly page: Page) {
    this.resolver = new LocatorResolver(page);
  }

  async expectLoaded(): Promise<void> {
    await this.resolver.resolve([...LOCATORS.productSearch.sku], 'P6_SKU');
  }

  async searchItemCode(itemCode: string): Promise<void> {
    const input = await this.resolver.resolve([...LOCATORS.productSearch.sku], 'P6_SKU');
    const search = await this.resolver.resolve([...LOCATORS.productSearch.search], 'search button');
    await input.fill(itemCode);
    await search.click();
  }

  async expectResultRegion(): Promise<void> {
    await this.page.locator('.t-Body-content, .t-Region, .a-IRR-table').first().waitFor({ state: 'visible' });
  }
}
