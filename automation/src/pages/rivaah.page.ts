import type { Page } from '@playwright/test';
import { appUrl } from '../core/app-url';
import { LOCATORS, LocatorResolver } from '../core/locator-chain';

export class RivaahPage {
  private readonly resolver: LocatorResolver;

  constructor(private readonly page: Page) {
    this.resolver = new LocatorResolver(page);
  }

  async openFromHome(homePage: { openRivaahFromNav: () => Promise<void> }): Promise<void> {
    await homePage.openRivaahFromNav();
    await this.expectCardsLoaded();
  }

  async openDirect(): Promise<void> {
    await this.page.goto(appUrl('rivaah'), { waitUntil: 'domcontentloaded' });
    await this.expectCardsLoaded();
  }

  async expectCardsLoaded(): Promise<void> {
    await this.page.locator('a.t-Card-wrap').first().waitFor({ state: 'visible', timeout: 30_000 });
  }

  async openCard(cardKey: keyof typeof LOCATORS.rivaah.cards): Promise<void> {
    const chain = [...LOCATORS.rivaah.cards[cardKey]];
    const card = await this.resolver.firstVisible(chain, `Rivaah card ${cardKey}`, 20_000);
    await card.scrollIntoViewIfNeeded();
    await card.click();
  }
}
