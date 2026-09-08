import type { Page } from '@playwright/test';
import { appUrl } from '../core/app-url';
import { dismissBlockingOverlays } from '../core/apex-overlays';
import { LOCATORS, LocatorResolver } from '../core/locator-chain';

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Match home card label exactly — avoids "Gold Coin Stock Visibility" when asking for "Stock Visibility". */
export function locateHomeCard(page: Page, cardText: string) {
  const exact = new RegExp(`^\\s*${escapeRegExp(cardText)}\\s*$`, 'i');
  return page.locator('a.custom-card-wrap, li.custom-card-item a').filter({ hasText: exact });
}

export class HomePage {
  private readonly resolver: LocatorResolver;

  constructor(private readonly page: Page) {
    this.resolver = new LocatorResolver(page);
  }

  async openCardByText(cardText: string, fallbackUrl?: string): Promise<void> {
    await dismissBlockingOverlays(this.page);
    await this.page.waitForURL(/\/home/i, { timeout: 15_000 });

    const card = locateHomeCard(this.page, cardText);

    try {
      await card.first().waitFor({ state: 'visible', timeout: 12_000 });
      await card.first().scrollIntoViewIfNeeded();
      await dismissBlockingOverlays(this.page);
      await card.first().click({ force: true, timeout: 10_000 });
      return;
    } catch {
      if (!fallbackUrl) throw new Error(`Home card "${cardText}" not found or not clickable`);
      await this.page.goto(fallbackUrl, { waitUntil: 'domcontentloaded', timeout: 60_000 });
    }
  }

  async openItemSearch(): Promise<void> {
    await this.openCardByText('Item Search', appUrl('product-detail-item-search?clear=6'));
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
    await this.page.waitForURL(/\/home/i, { timeout: 15_000 }).catch(() => undefined);

    try {
      const menu = await this.resolver.firstVisible([...LOCATORS.userMenu.menu], 'user menu', 10_000);
      await menu.click({ force: true });
      await dismissBlockingOverlays(this.page);
      const signOut = await this.resolver.firstVisible([...LOCATORS.userMenu.signOut], 'sign out', 10_000);
      await signOut.click({ force: true });
    } catch {
      await this.page.evaluate(() => {
        const menuBtn = document.querySelector<HTMLElement>('#L21731618447730172, [data-menu*="menu_L"]');
        menuBtn?.click();
        const link = document.querySelector<HTMLAnchorElement>("a[href*='apex_authentication.logout']");
        link?.click();
      });
    }

    await this.page.waitForURL(/login/i, { timeout: 30_000 });
    await dismissBlockingOverlays(this.page);
  }

  async openCustomerDrawer(): Promise<void> {
    await dismissBlockingOverlays(this.page);
    await this.page.waitForURL(/\/home/i, { timeout: 15_000 }).catch(() => undefined);
    const customer = await this.resolver.firstVisible([...LOCATORS.home.customer], 'customer selector', 10_000);
    await customer.click({ force: true });
  }

  async openSettings(): Promise<void> {
    await dismissBlockingOverlays(this.page);
    const menu = await this.resolver.firstVisible([...LOCATORS.userMenu.menu], 'user menu', 10_000);
    await menu.click({ force: true });
    await dismissBlockingOverlays(this.page);
    const settings = await this.resolver.firstVisible([...LOCATORS.userMenu.settings], 'settings', 10_000);
    await settings.click({ force: true });
  }
}
