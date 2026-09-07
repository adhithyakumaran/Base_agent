import { test as base, expect } from '@playwright/test';
import { homePath } from '../core/app-url';
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
};

export const test = base.extend<Fixtures>({
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
    await page.goto(homePath());
    await expect(page).toHaveURL(/\/home/i);
    await use(homePage);
  },
});

export { expect };
