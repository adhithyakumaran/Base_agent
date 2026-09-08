import type { Page } from '@playwright/test';
import { appUrl } from '../core/app-url';
import { dismissBlockingOverlays } from '../core/apex-overlays';
import { LOCATORS, LocatorResolver } from '../core/locator-chain';

export class HomePage {
  private readonly resolver: LocatorResolver;

  constructor(private readonly page: Page) {
    this.resolver = new LocatorResolver(page);
  }

  async openCardByText(cardText: string, fallbackUrl?: string): Promise<void> {
    await dismissBlockingOverlays(this.page);
    await this.page.waitForURL(/\/home/i, { timeout: 15_000 });

    const card = this.page
      .locator('a.custom-card-wrap, li.custom-card-item a')
      .filter({ hasText: cardText })
      .first();

    try {
      await card.waitFor({ state: 'visible', timeout: 12_000 });
      await card.scrollIntoViewIfNeeded();
      await dismissBlockingOverlays(this.page);
      await card.click({ force: true, timeout: 10_000 });
      return;
    } catch {
      if (!fallbackUrl) throw new Error(`Home card "${cardText}" not found or not clickable`);
      await this.page.goto(fallbackUrl, { waitUntil: 'domcontentloaded', timeout: 60_000 });
    }
  }

  async openItemSearch(): Promise<void> {
    await this.openCardByText('Item Search', appUrl('product-detail-item-search'));
  }

  async openProductStockVisibility(): Promise<void> {
    await this.openCardByText('Stock Visibility', appUrl('product-stock-visibility?clear=114'));
  }

  async openRivaahFromNav(): Promise<void> {
    await dismissBlockingOverlays(this.page);
    await this.page.waitForURL(/\/home/i, { timeout: 15_000 });

    const nav = await this.resolver.firstVisible(
      [
        ...LOCATORS.rivaah.nav,
        'a.a-MenuBar-label:has-text("Rivaah")',
        '.t-Header-nav-list a:has-text("Rivaah")',
        'text=Rivaah',
      ],
      'Rivaah nav',
      15_000
    );
    await nav.click({ force: true });
  }

  async signOut(): Promise<void> {
    await dismissBlockingOverlays(this.page);
    const menu = await this.resolver.firstVisible([...LOCATORS.userMenu.menu], 'user menu', 10_000);
    await menu.click();
    const signOut = await this.resolver.firstVisible([...LOCATORS.userMenu.signOut], 'sign out', 10_000);
    await signOut.click();
    await this.page.waitForURL(/login/i, { timeout: 30_000 }).catch(() => undefined);
    await dismissBlockingOverlays(this.page);
  }

  async openCustomerDrawer(): Promise<void> {
    await dismissBlockingOverlays(this.page);
    const customer = await this.resolver.firstVisible([...LOCATORS.home.customer], 'customer selector', 10_000);
    await customer.click();
  }

  async openSettings(): Promise<void> {
    await dismissBlockingOverlays(this.page);
    const menu = await this.resolver.firstVisible([...LOCATORS.userMenu.menu], 'user menu', 10_000);
    await menu.click();
    const settings = await this.resolver.firstVisible([...LOCATORS.userMenu.settings], 'settings', 10_000);
    await settings.click();
  }
}
