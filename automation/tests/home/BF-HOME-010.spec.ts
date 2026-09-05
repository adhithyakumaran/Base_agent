import { test, expect } from '../../src/fixtures/test-base';

test.describe('BF-HOME-010 Home Navigation Map @BF-HOME-010 @regression @navigation', () => {
  test('TC-BF-HOME-010-P01 home loads with navigation and cards @sanity', async ({ authenticatedPage, page }) => {
    await expect(page).toHaveURL(/\/home/i);
    await expect(page.locator('a.custom-card-wrap').first()).toBeVisible();
    await expect(page.locator('text=Endless Aisle').first()).toBeVisible();
  });

  test('TC-BF-HOME-010-E01 item search card navigates away from home @regression', async ({
    authenticatedPage,
    page,
  }) => {
    await authenticatedPage.openItemSearch();
    await expect(page).not.toHaveURL(/\/home$/i);
  });
});
