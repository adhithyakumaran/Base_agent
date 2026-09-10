import type { Page } from '@playwright/test';
import { appUrl } from '../core/app-url';
import { dismissBlockingOverlays } from '../core/apex-overlays';
import { LOCATORS, LocatorResolver } from '../core/locator-chain';
import type { HomePage } from './home.page';

export class RivaahPage {
  private readonly resolver: LocatorResolver;

  constructor(private readonly page: Page) {
    this.resolver = new LocatorResolver(page);
  }

  /** Prefer top-nav (matches real user path); fall back to direct URL with APEX page reset. */
  async open(homePage?: HomePage): Promise<void> {
    await dismissBlockingOverlays(this.page);

    if (homePage && /\/home/i.test(this.page.url())) {
      try {
        await homePage.openRivaahFromNav();
        await this.page.waitForURL(/rivaah/i, { timeout: 45_000, waitUntil: 'domcontentloaded' });
        await this.expectCardsLoaded();
        return;
      } catch {
        // fall through to direct navigation
      }
    }

    await this.page.goto(appUrl('rivaah?clear=38'), { waitUntil: 'load', timeout: 60_000 });
    await dismissBlockingOverlays(this.page);
    await this.expectCardsLoaded();
  }

  async openFromHome(homePage: HomePage): Promise<void> {
    await this.open(homePage);
  }

  async expectCardsLoaded(): Promise<void> {
    if (/\/login/i.test(this.page.url())) {
      throw new Error(`Rivaah requires login — landed on ${this.page.url()}`);
    }

    await this.resolver.firstVisible(
      [
        'a.t-Card-wrap',
        'li.t-Cards-item a.t-Card-wrap',
        'h3.t-Card-title',
        'text=Wedding Trousseau Styling',
        'text=Engagement Rings',
        '.t-Body-content',
      ],
      'Rivaah cards',
      35_000
    );
  }

  async openCard(cardKey: keyof typeof LOCATORS.rivaah.cards): Promise<void> {
    await dismissBlockingOverlays(this.page);
    const chain = [...LOCATORS.rivaah.cards[cardKey]];
    const card = await this.resolver.firstVisible(chain, `Rivaah card ${cardKey}`, 25_000);
    await card.scrollIntoViewIfNeeded();
    await card.click({ force: true });
  }
}
