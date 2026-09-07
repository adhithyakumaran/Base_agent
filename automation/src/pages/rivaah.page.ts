import type { Page } from '@playwright/test';
import { appUrl } from '../core/app-url';
import { dismissBlockingOverlays } from '../core/apex-overlays';
import { LOCATORS, LocatorResolver } from '../core/locator-chain';

export class RivaahPage {
  private readonly resolver: LocatorResolver;

  constructor(private readonly page: Page) {
    this.resolver = new LocatorResolver(page);
  }

  /** Open Rivaah via direct URL — reliable when nav menu id differs per session. */
  async open(): Promise<void> {
    await dismissBlockingOverlays(this.page);
    await this.page.goto(appUrl('rivaah'), { waitUntil: 'domcontentloaded', timeout: 60_000 });
    await this.expectCardsLoaded();
  }

  async openFromHome(homePage: { openRivaahFromNav: () => Promise<void> }): Promise<void> {
    try {
      if (/\/home/i.test(this.page.url())) {
        await homePage.openRivaahFromNav();
      } else {
        await this.open();
        return;
      }
    } catch {
      await this.open();
      return;
    }
    await this.expectCardsLoaded();
  }

  async expectCardsLoaded(): Promise<void> {
    await this.page.locator('a.t-Card-wrap').first().waitFor({ state: 'visible', timeout: 30_000 });
  }

  async openCard(cardKey: keyof typeof LOCATORS.rivaah.cards): Promise<void> {
    await dismissBlockingOverlays(this.page);
    const chain = [...LOCATORS.rivaah.cards[cardKey]];
    const card = await this.resolver.firstVisible(chain, `Rivaah card ${cardKey}`, 25_000);
    await card.scrollIntoViewIfNeeded();
    await card.click({ force: true });
  }
}
