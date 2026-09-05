import type { Page } from '@playwright/test';
import { LOCATORS, LocatorResolver } from '../core/locator-chain';

export class HomePage {
  private readonly resolver: LocatorResolver;

  constructor(private readonly page: Page) {
    this.resolver = new LocatorResolver(page);
  }

  async openCardByText(cardText: string): Promise<void> {
    const card = this.page.locator('a.custom-card-wrap').filter({ hasText: cardText }).first();
    await card.click();
  }

  async openItemSearch(): Promise<void> {
    await this.openCardByText('Item Search');
  }

  async openProductStockVisibility(): Promise<void> {
    await this.openCardByText('Stock Visibility');
  }

  async openRivaahFromNav(): Promise<void> {
    const nav = await this.resolver.firstVisible([...LOCATORS.rivaah.nav], 'Rivaah nav');
    await nav.click();
  }

  async signOut(): Promise<void> {
    const menu = await this.resolver.resolve([...LOCATORS.userMenu.menu], 'user menu');
    await menu.click();
    const signOut = await this.resolver.resolve([...LOCATORS.userMenu.signOut], 'sign out');
    await signOut.click();
  }

  async openCustomerDrawer(): Promise<void> {
    const customer = await this.resolver.firstVisible([...LOCATORS.home.customer], 'customer selector');
    await customer.click();
  }

  async openSettings(): Promise<void> {
    const menu = await this.resolver.resolve([...LOCATORS.userMenu.menu], 'user menu');
    await menu.click();
    const settings = await this.resolver.resolve([...LOCATORS.userMenu.settings], 'settings');
    await settings.click();
  }
}
