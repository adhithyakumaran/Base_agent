/**
 * Live demo fixtures — persistent Chrome profile + page objects for real headed runs.
 */
import { test as base, expect, chromium, type BrowserContext, type Page } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { captureStepEvidence, wrapPageWithEvidence } from '../core/evidence';
import { emitLiveEvent } from '../core/live-events';
import { loginUrl, normalizeBaseUrl } from '../core/app-url';
import { performLogin } from '../core/login-setup';
import { ensureAuthenticated } from './auth';
import { LoginPage } from '../pages/login.page';
import { HomePage } from '../pages/home.page';
import { ProductSearchPage } from '../pages/product-search.page';
import { StockVisibilityPage } from '../pages/stock-visibility.page';

const keepOpen = () => process.env.QA_KEEP_BROWSER_OPEN === 'true';

async function launchLiveContext(): Promise<BrowserContext> {
  const profileDir =
    process.env.QA_LIVE_PROFILE_DIR || path.resolve('reports/browser-profiles/default-live');
  fs.mkdirSync(profileDir, { recursive: true });
  const channel = process.env.QA_BROWSER_CHANNEL || process.env.EA_BROWSER_CHANNEL || 'chrome';
  const headless = process.env.QA_BROWSER_HEADLESS === 'true';
  const slowMo = Number(process.env.QA_LIVE_ACTION_DELAY_MS || 0);
  try {
    return await chromium.launchPersistentContext(profileDir, {
      channel,
      headless,
      slowMo,
      args: ['--disable-blink-features=AutomationControlled'],
      viewport: { width: 1366, height: 768 },
      ignoreHTTPSErrors: process.env.EA_IGNORE_HTTPS_ERRORS === 'true',
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`BROWSER_UNAVAILABLE: ${message}`);
  }
}

type Fixtures = {
  liveContext: BrowserContext;
  loginPage: LoginPage;
  homePage: HomePage;
  productSearchPage: ProductSearchPage;
  stockVisibilityPage: StockVisibilityPage;
  authenticatedPage: HomePage;
  recordStep: (label: string) => Promise<void>;
};

export const test = base.extend<Fixtures>({
  liveContext: [
    async ({}, use) => {
      const context = await launchLiveContext();
      await emitLiveEvent({ phase: 'BROWSER', action: 'LAUNCH', status: 'OK' });
      await use(context);
      if (!keepOpen()) {
        await context.close();
      } else {
        await emitLiveEvent({
          phase: 'BROWSER',
          action: 'KEEP_OPEN',
          status: 'OK',
          value_summary: 'Browser remains open for inspection.',
        });
      }
    },
    { scope: 'worker' },
  ],
  page: async ({ liveContext }, use, testInfo) => {
    const flowId = process.env.QA_FLOW_ID || '';
    const title = flowId ? `ScoutAI Live QA — ${flowId}` : 'ScoutAI Live QA';
    let page = liveContext.pages()[0];
    if (!page) {
      page = await liveContext.newPage();
    }
    await page.setViewportSize({ width: 1366, height: 768 });
    try {
      await page.setTitle(title);
    } catch {
      /* ignore */
    }
    wrapPageWithEvidence(page, testInfo, { liveEvents: true });
    const baseURL = normalizeBaseUrl(process.env.EA_BASE_URL || '');
    const user = process.env.EA_USER_USERNAME;
    const pass = process.env.EA_USER_PASSWORD;
    if (baseURL && user && pass && process.env.EA_SKIP_GLOBAL_SETUP === 'true') {
      const target = loginUrl();
      await emitLiveEvent({ phase: 'NAVIGATE', action: 'OPEN', target });
      await page.goto(target, { waitUntil: 'load', timeout: 90_000 });
      await emitLiveEvent({ phase: 'LOGIN', action: 'AUTHENTICATE', value_summary: '[redacted]' });
      await performLogin(page, user, pass);
      await page.bringToFront();
    }
    await captureStepEvidence(page, testInfo, 'test-start');
    await use(page);
    await captureStepEvidence(page, testInfo, 'test-end');
    if (!keepOpen()) {
      await page.close();
    } else {
      await page.bringToFront();
    }
  },
  recordStep: async ({ page }, use, testInfo) => {
    await use(async (label: string) => {
      await captureStepEvidence(page, testInfo, label);
    });
  },
  loginPage: async ({ page }, use) => {
    await use(new LoginPage(page));
  },
  homePage: async ({ page }, use) => {
    await use(new HomePage(page));
  },
  productSearchPage: async ({ page }, use) => {
    await use(new ProductSearchPage(page));
  },
  stockVisibilityPage: async ({ page }, use) => {
    await use(new StockVisibilityPage(page));
  },
  authenticatedPage: async ({ page, homePage }, use) => {
    const user = process.env.EA_USER_USERNAME;
    const pass = process.env.EA_USER_PASSWORD;
    if (!user || !pass) {
      test.skip(true, 'EA_USER_USERNAME / EA_USER_PASSWORD not configured');
    }
    await ensureAuthenticated(page);
    await expect(page).toHaveURL(/\/home/i, { timeout: 30_000 });
    await use(homePage);
  },
});

export { expect };
