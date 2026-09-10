import { test as base, expect } from '@playwright/test';
import { captureStepEvidence, wrapPageWithEvidence } from '../core/evidence';
import { ensureAuthenticated } from './auth';
import { LoginPage } from '../pages/login.page';
import { HomePage } from '../pages/home.page';
import { ProductSearchPage } from '../pages/product-search.page';
import { StockVisibilityPage } from '../pages/stock-visibility.page';

type Fixtures = {
  loginPage: LoginPage;
  homePage: HomePage;
  productSearchPage: ProductSearchPage;
  stockVisibilityPage: StockVisibilityPage;
  authenticatedPage: HomePage;
  recordStep: (label: string) => Promise<void>;
};

export const test = base.extend<Fixtures>({
  page: async ({ page }, use, testInfo) => {
    wrapPageWithEvidence(page, testInfo);
    await captureStepEvidence(page, testInfo, 'test-start');
    await use(page);
    await captureStepEvidence(page, testInfo, 'test-end');
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
export { ensureAuthenticated, refreshAuthStorage } from './auth';
export { gotoApp, gotoAppUrl, gotoHome, gotoLogin } from './navigation';
