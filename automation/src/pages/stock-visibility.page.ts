import type { Page } from '@playwright/test';
import { appUrl } from '../core/app-url';
import { dismissBlockingOverlays } from '../core/apex-overlays';
import { LOCATORS, LocatorResolver } from '../core/locator-chain';

export class StockVisibilityPage {
  private readonly resolver: LocatorResolver;

  constructor(private readonly page: Page) {
    this.resolver = new LocatorResolver(page);
  }

  /** Open stock visibility — direct APEX URL with page reset is most reliable in long suites. */
  async open(): Promise<void> {
    await dismissBlockingOverlays(this.page);
    await this.page.goto(appUrl('product-stock-visibility?clear=114'), {
      waitUntil: 'domcontentloaded',
      timeout: 60_000,
    });
    await this.expectLoaded();
  }

  async expectLoaded(): Promise<void> {
    if (/\/login/i.test(this.page.url())) {
      throw new Error(`Stock Visibility redirected to login — ${this.page.url()}`);
    }

    try {
      await this.resolver.firstVisible([...LOCATORS.stockVisibility.sku], 'stock sku input', 25_000);
      return;
    } catch {
      // Legacy route (recordings used ea1/47 + P47_SKU)
      await this.page.goto(appUrl('ea1/47?clear=47'), { waitUntil: 'domcontentloaded', timeout: 60_000 }).catch(() => undefined);
      await dismissBlockingOverlays(this.page);
    }

    try {
      await this.resolver.firstVisible([...LOCATORS.stockVisibility.sku], 'stock sku input', 20_000);
    } catch (error) {
      const title = await this.page.title().catch(() => 'unknown');
      throw new Error(
        `Stock Visibility page did not expose a SKU field (url=${this.page.url()}, title=${title}). ` +
          `Confirm BALA can open Product Stock Visibility from Home in the browser.`
      );
    }
  }

  async searchItemCode(itemCode: string): Promise<void> {
    const input = await this.resolver.firstVisible([...LOCATORS.stockVisibility.sku], 'stock sku input', 20_000);
    const search = await this.resolver.firstVisible([...LOCATORS.stockVisibility.search], 'stock search', 10_000);
    await input.fill(itemCode);
    await search.click();
  }
}
