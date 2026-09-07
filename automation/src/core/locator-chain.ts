import type { Locator, Page } from '@playwright/test';

export type LocatorChain = string[];

export class LocatorResolver {
  constructor(private readonly page: Page) {}

  async resolve(chain: LocatorChain, label: string): Promise<Locator> {
    for (const selector of chain) {
      const locator = this.page.locator(selector);
      const count = await locator.count();
      if (count === 1) return locator;
      if (count > 1) {
        throw new Error(`Ambiguous locator for ${label}: ${selector} matched ${count}`);
      }
    }
    throw new Error(`No locator resolved for ${label}: ${chain.join(' -> ')}`);
  }

  async firstVisible(chain: LocatorChain, label: string, timeoutMs = 5000): Promise<Locator> {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      for (const selector of chain) {
        const locator = this.page.locator(selector);
        const count = await locator.count();
        if (count >= 1) {
          const candidate = locator.first();
          if (await candidate.isVisible().catch(() => false)) return candidate;
        }
      }
      await this.page.waitForTimeout(200);
    }
    return this.resolve(chain, label);
  }
}

export const LOCATORS = {
  login: {
    username: [
      '#P9999_USERNAME',
      'input[name="P9999_USERNAME"]',
      'input[placeholder="Username"]',
      'input[placeholder*="Username" i]',
    ],
    password: [
      '#P9999_PASSWORD',
      'input[name="P9999_PASSWORD"]',
      'input[autocomplete="current-password"]',
      'input[placeholder="Password"]',
      'input[placeholder*="Password" i]',
    ],
    submit: [
      '#login-btn',
      'button#login-btn',
      'button.t-Button--hot#login-btn',
      'button.t-Button--hot:has-text("LOGIN")',
      'button:has-text("LOGIN")',
      'button:has-text("Login")',
      'input[type="button"][value*="LOGIN" i]',
    ],
  },
  userMenu: {
    menu: ['#L21731618447730172', "button[id='L21731618447730172']"],
    signOut: ['#menu_L21731618447730172_2i', 'a:has-text("Sign Out")', "a[href*='apex_authentication.logout']"],
    settings: ['#menu_L21731618447730172_0', 'text=Settings'],
  },
  productSearch: {
    sku: ['#P6_SKU', "input[name='P6_SKU']", "input[placeholder='Enter item code or scan the QR']"],
    search: ['#btn_search', 'button[title="Search"]', 'button[aria-label="Search"]'],
    scan: ['#B24029796092184015', 'button[aria-label="Scan"]'],
  },
  stockVisibility: {
    sku: [
      '#P114_SKU',
      "input[name='P114_SKU']",
      'input#P114_SKU',
      'input[placeholder*="Item code" i]',
      'input[placeholder*="14 Digit" i]',
    ],
    search: ['#P47_SEARCH', 'button#P47_SEARCH', 'button:has-text("Search")', "[id='P47_SEARCH']"],
  },
  home: {
    storeStock: ['#B74402876591024608', 'button:has-text("STORE STOCK")'],
    customer: ['text=Customer ( Click to Select )', 'a:has-text("Customer")'],
    orso: ['text=ORSO Recommendation'],
  },
  rivaah: {
    nav: ['#t_MenuNav_3i', "a[role='menuitem'][id='t_MenuNav_3i']", 'text=Rivaah'],
    back: ['#B50666671840999844', 'button#B50666671840999844', 'button:has-text("Back")'],
    cards: {
      trousseauStyling: [
        "a.t-Card-wrap[href*='wedding-trousseau?']",
        "a.t-Card-wrap[href*='wedding-trousseau']",
        'a.t-Card-wrap:has-text("Wedding Trousseau Styling")',
      ],
      trousseauSetImage: [
        "a.t-Card-wrap[href*='wedding-trousseau1']",
        'a.t-Card-wrap:has-text("Trousseau Set Image")',
      ],
      engagementRings: [
        "a.t-Card-wrap[href*='standard-product-search']",
        'a.t-Card-wrap:has-text("Engagement Rings")',
      ],
      weddingExperts: [
        "a.t-Card-wrap[href*='wedding-experts']",
        'a.t-Card-wrap:has-text("Wedding Experts")',
      ],
      weddingWishlist: [
        "a.t-Card-wrap[href*='dreams-in-gold']",
        'a.t-Card-wrap:has-text("Wedding Wishlist")',
        'a.t-Card-wrap:has-text("Dreams in Gold")',
      ],
    },
  },
} as const;
