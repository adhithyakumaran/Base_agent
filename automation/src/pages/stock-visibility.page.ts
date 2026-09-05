import type { Page } from '@playwright/test';
import { LOCATORS, LocatorResolver } from '../core/locator-chain';

export class StockVisibilityPage {
  private readonly resolver: LocatorResolver;

  constructor(private readonly page: Page) {
    this.resolver = new LocatorResolver(page);
  }

  async expectLoaded(): Promise<void> {
    await this.resolver.resolve([...LOCATORS.stockVisibility.sku], 'P114_SKU');
  }

  async searchItemCode(itemCode: string): Promise<void> {
    const input = await this.resolver.resolve([...LOCATORS.stockVisibility.sku], 'P114_SKU');
    const search = await this.resolver.resolve([...LOCATORS.stockVisibility.search], 'P47_SEARCH');
    await input.fill(itemCode);
    await search.click();
  }
}
