import { test, expect } from '../../src/fixtures/test-base';
import { attachEvidence } from '../../src/core/evidence';

test.describe('BF-LOGOUT-002 User Logout @BF-LOGOUT-002 @regression @authentication', () => {
  test('TC-BF-LOGOUT-002-P01 sign out returns to login @sanity', async ({ authenticatedPage, page }, testInfo) => {
    await authenticatedPage.signOut();
    await expect(page).toHaveURL(/login/i);
    await attachEvidence(page, testInfo, 'post-logout');
  });

  test('TC-BF-LOGOUT-002-E01 back navigation after logout requires re-auth @regression', async ({
    authenticatedPage,
    page,
  }) => {
    await authenticatedPage.signOut();
    await expect(page).toHaveURL(/login/i);
    await page.goBack().catch(() => undefined);
    await expect(page).toHaveURL(/login/i);
  });
});
