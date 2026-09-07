import { test, expect, ensureAuthenticated } from '../../src/fixtures/test-base';
import { RivaahPage } from '../../src/pages/rivaah.page';

test.beforeEach(async ({ page }) => {
  await ensureAuthenticated(page);
});

test.describe('BF-RIVAAH-005 Rivaah @BF-RIVAAH-005 @regression @rivaah', () => {
  test('TC-BF-RIVAAH-005-P01 rivaah page loads from nav @sanity', async ({ authenticatedPage, page }) => {
    const rivaah = new RivaahPage(page);
    await rivaah.openFromHome(authenticatedPage);
    await expect(page).toHaveURL(/rivaah/i);
  });
});

test.describe('BF-RIVAAH-005-01 Wedding Trousseau @BF-RIVAAH-005-01 @regression @rivaah', () => {
  test('TC-BF-RIVAAH-005-01-P01 trousseau styling card navigates @sanity', async ({ authenticatedPage, page }) => {
    const rivaah = new RivaahPage(page);
    await rivaah.openFromHome(authenticatedPage);
    await rivaah.openCard('trousseauStyling');
    await expect(page).toHaveURL(/wedding-trousseau/i);
  });
});

test.describe('BF-RIVAAH-005-02 Trousseau Set Image @BF-RIVAAH-005-02 @regression @rivaah', () => {
  test('TC-BF-RIVAAH-005-02-P01 set image entry @sanity', async ({ authenticatedPage, page }) => {
    const rivaah = new RivaahPage(page);
    await rivaah.openFromHome(authenticatedPage);
    await rivaah.openCard('trousseauSetImage');
    await expect(page).toHaveURL(/wedding-trousseau1/i);
  });
});

test.describe('BF-RIVAAH-005-03 Engagement Rings @BF-RIVAAH-005-03 @regression @rivaah', () => {
  test('TC-BF-RIVAAH-005-03-P01 engagement rings opens product search @sanity', async ({ authenticatedPage, page }) => {
    const rivaah = new RivaahPage(page);
    await rivaah.openFromHome(authenticatedPage);
    await rivaah.openCard('engagementRings');
    await expect(page).toHaveURL(/standard-product-search/i);
  });
});

test.describe('BF-RIVAAH-005-04 Wedding Experts @BF-RIVAAH-005-04 @regression @rivaah', () => {
  test('TC-BF-RIVAAH-005-04-P01 wedding experts entry @sanity', async ({ authenticatedPage, page }) => {
    const rivaah = new RivaahPage(page);
    await rivaah.openFromHome(authenticatedPage);
    await rivaah.openCard('weddingExperts');
    await expect(page).toHaveURL(/wedding-experts/i);
  });
});

test.describe('BF-RIVAAH-005-05 Wedding Wishlist @BF-RIVAAH-005-05 @regression @rivaah', () => {
  test('TC-BF-RIVAAH-005-05-P01 wishlist entry shows customer validation @sanity', async ({ authenticatedPage, page }) => {
    const rivaah = new RivaahPage(page);
    await rivaah.openFromHome(authenticatedPage);
    await rivaah.openCard('weddingWishlist');
    await expect(page).toHaveURL(/dreams-in-gold/i);
  });
});
