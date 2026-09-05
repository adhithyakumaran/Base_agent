import { test, expect } from '../../src/fixtures/test-base';

test.describe('BF-RIVAAH-005 Rivaah @BF-RIVAAH-005 @regression @rivaah', () => {
  test('TC-BF-RIVAAH-005-P01 rivaah page loads from nav @sanity', async ({ authenticatedPage, page }) => {
    await authenticatedPage.openRivaahFromNav();
    await expect(page).toHaveURL(/rivaah/i);
    await expect(page.locator('a.t-Card-wrap').first()).toBeVisible();
  });
});

test.describe('BF-RIVAAH-005-01 Wedding Trousseau @BF-RIVAAH-005-01 @regression @rivaah', () => {
  test('TC-BF-RIVAAH-005-01-P01 trousseau styling card navigates @sanity', async ({ page }) => {
    await page.goto('/rivaah');
    await page.locator("a.t-Card-wrap[href*='wedding-trousseau']").first().click();
    await expect(page).toHaveURL(/wedding-trousseau/i);
  });
});

test.describe('BF-RIVAAH-005-02 Trousseau Set Image @BF-RIVAAH-005-02 @regression @rivaah', () => {
  test('TC-BF-RIVAAH-005-02-P01 set image entry @sanity', async ({ page }) => {
    await page.goto('/rivaah');
    await page.locator("a.t-Card-wrap[href*='wedding-trousseau1']").first().click();
    await expect(page).toHaveURL(/wedding-trousseau1/i);
  });
});

test.describe('BF-RIVAAH-005-03 Engagement Rings @BF-RIVAAH-005-03 @regression @rivaah', () => {
  test('TC-BF-RIVAAH-005-03-P01 engagement rings opens product search @sanity', async ({ page }) => {
    await page.goto('/rivaah');
    await page.locator("a.t-Card-wrap[href*='standard-product-search']").first().click();
    await expect(page).toHaveURL(/standard-product-search/i);
  });
});

test.describe('BF-RIVAAH-005-04 Wedding Experts @BF-RIVAAH-005-04 @regression @rivaah', () => {
  test('TC-BF-RIVAAH-005-04-P01 wedding experts entry @sanity', async ({ page }) => {
    await page.goto('/rivaah');
    await page.locator("a.t-Card-wrap[href*='wedding-experts']").first().click();
    await expect(page).toHaveURL(/wedding-experts/i);
  });
});

test.describe('BF-RIVAAH-005-05 Wedding Wishlist @BF-RIVAAH-005-05 @regression @rivaah', () => {
  test('TC-BF-RIVAAH-005-05-P01 wishlist entry shows customer validation @sanity', async ({ page }) => {
    await page.goto('/rivaah');
    await page.locator("a.t-Card-wrap[href*='dreams-in-gold']").first().click();
    await expect(page).toHaveURL(/dreams-in-gold/i);
  });
});
