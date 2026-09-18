import type { Locator, Page } from '@playwright/test';
import { resolveLocatorChain, type OverlayUsageMeta } from './healing-overlays';

export type LocatorChain = string[];

export type { OverlayUsageMeta };

export class LocatorResolver {
  private lastUsage: OverlayUsageMeta | undefined;

  constructor(private readonly page: Page) {}

  getLastOverlayUsage(): OverlayUsageMeta | undefined {
    return this.lastUsage;
  }

  async resolve(chain: LocatorChain, label: string): Promise<Locator> {
    const resolved = resolveLocatorChain(chain, label);
    this.lastUsage = resolved.meta;
    chain = resolved.chain;
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
    const resolved = resolveLocatorChain(chain, label);
    this.lastUsage = resolved.meta;
    chain = resolved.chain;
    const timingBoost = Number(process.env.QA_HEALING_TIMING_MS || 0);
    const deadline = Date.now() + timeoutMs + timingBoost;
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
    itemIdentity: ['#P6_ITEM', "input[name='P6_ITEM']", "input[id='P6_ITEM']"],
    resultRegion: [
      '.t-Body-content .t-Region-body',
      '.t-Body-content .a-Report-report',
      '.t-Body-content .t-Form-fieldContainer',
      '.t-Body-content',
    ],
    stockStatus: [
      'text=/Sold Out/i',
      'text=/Not in Stock/i',
      'text=/No Stock/i',
      'text=/STORE STOCK/i',
      'text=/Factory/i',
    ],
    openDetail: [
      "a[href*='/ea/product-detail']:not([href*='product-detail-item-search'])",
      "button:has-text('View Product')",
      "button:has-text('View Details')",
      "a:has-text('View Product')",
      "a:has-text('View Details')",
      '.t-Body-content a[href*="product-detail"] img',
      '.t-Body-content .t-Region-body a',
      '.t-Body-content img[alt*="product" i]',
    ],
  },
  productDetail: {
    detailPagePath: /\/ea\/product-detail(?:[/?#]|$)/i,
    identifier: [
      'text=/Item\\s*Code/i',
      'text=/SKU/i',
      '[class*="item" i][class*="code" i]',
      '.t-Body-content',
    ],
    imagery: ['.t-Body-content img', 'section.fs.gallery img', 'img.pimg', 'img[src*="product" i]'],
    price: ['text=/Price/i', 'text=/MRP/i', 'text=/₹/', 'text=/INR/i'],
    availability: [
      'text=/Sold Out/i',
      'text=/Not in Stock/i',
      'text=/No Stock/i',
      'text=/In Stock/i',
      'text=/STORE STOCK/i',
    ],
    backToProducts: ['text=/Back to Products/i', 'button:has-text("Back to Products")', 'a:has-text("Back to Products")'],
  },
  stockVisibility: {
    sku: [
      '#P114_SKU',
      "input[name='P114_SKU']",
      'input#P114_SKU',
      '#P47_SKU',
      "input[name='P47_SKU']",
      'input#P47_SKU',
      'input[placeholder*="Item code" i]',
      'input[placeholder*="14 Digit" i]',
      'input[placeholder*="14 digit" i]',
    ],
    search: [
      '#P47_SEARCH',
      'button#P47_SEARCH',
      'button:has-text("Search")',
      "[id='P47_SEARCH']",
      'button.t-Button--hot:has-text("Search")',
    ],
  },
  home: {
    storeStock: ['#B74402876591024608', 'button:has-text("STORE STOCK")'],
    customer: ['text=Customer ( Click to Select )', 'a:has-text("Customer")'],
    orso: ['text=ORSO Recommendation'],
  },
  rivaah: {
    nav: [
      '#t_MenuNav_3i',
      "a[role='menuitem'][id='t_MenuNav_3i']",
      'a.a-MenuBar-label:has-text("Rivaah")',
      'a.a-MenuBar-label[aria-current="true"]',
      '.t-Header-nav-list a:has-text("Rivaah")',
      'text=Rivaah',
    ],
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
        'a.t-Card-wrap:has-text("Rivaah Wedding Wishlist")',
        'a.t-Card-wrap:has-text("Wedding Wishlist")',
        'a.t-Card-wrap:has-text("Dreams in Gold")',
      ],
    },
  },
} as const;
