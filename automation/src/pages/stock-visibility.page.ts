import type { Page } from '@playwright/test';
import { LOCATORS, LocatorResolver } from '../core/locator-chain';

export class StockVisibilityPage {
  private readonly resolver: LocatorResolver;

  constructor(private readonly page: Page) {
    this.resolver = new LocatorResolver(page);
  }

  async expectLoaded(): Promise<void> {
    await this.resolver.firstVisible([...LOCATORS.stockVisibility.sku], 'stock sku input', 20_000);
  }

  async searchItemCode(itemCode: string): Promise<void> {
    const input = await this.resolver.firstVisible([...LOCATORS.stockVisibility.sku], 'stock sku input', 20_000);
    const search = await this.resolver.firstVisible([...LOCATORS.stockVisibility.search], 'stock search', 10_000);
    await input.fill(itemCode);
    await search.click();
  }
}
