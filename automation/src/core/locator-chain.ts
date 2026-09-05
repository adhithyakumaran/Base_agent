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
        if (count === 1 && (await locator.isVisible().catch(() => false))) return locator;
      }
      await this.page.waitForTimeout(200);
    }
    return this.resolve(chain, label);
  }
}

export const LOCATORS = {
  login: {
    username: ['#P9999_USERNAME', 'input[name="P9999_USERNAME"]', 'input[placeholder="Username"]'],
    password: ['#P9999_PASSWORD', 'input[name="P9999_PASSWORD"]', 'input[autocomplete="current-password"]'],
    submit: ['#login-btn', 'button#login-btn', 'button:has-text("Login")'],
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
    sku: ['#P114_SKU', "input[name='P114_SKU']", 'input#P114_SKU'],
    search: ['#P47_SEARCH', 'button#P47_SEARCH', "[id='P47_SEARCH']"],
  },
  home: {
    storeStock: ['#B74402876591024608', 'button:has-text("STORE STOCK")'],
    customer: ['text=Customer ( Click to Select )', 'a:has-text("Customer")'],
    orso: ['text=ORSO Recommendation'],
  },
  rivaah: {
    nav: ['#t_MenuNav_3i', "a[role='menuitem'][id='t_MenuNav_3i']", 'text=Rivaah'],
    back: ['#B50666671840999844', 'button#B50666671840999844', 'button:has-text("Back")'],
  },
} as const;
