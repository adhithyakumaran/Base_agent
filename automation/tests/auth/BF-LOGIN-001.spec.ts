import { test, expect } from '../../src/fixtures/test-base';
import { attachEvidence } from '../../src/core/evidence';

test.use({ storageState: { cookies: [], origins: [] } });

test.describe('BF-LOGIN-001 User Login @BF-LOGIN-001 @regression @authentication', () => {
  test('TC-BF-LOGIN-001-P01 valid credentials reach home @sanity', async ({ loginPage, page }, testInfo) => {
    const user = process.env.EA_USER_USERNAME;
    const pass = process.env.EA_USER_PASSWORD;
    test.skip(!user || !pass, 'Credentials not configured in automation/config/.env');

    await loginPage.goto();
    await loginPage.login(user!, pass!);
    await expect(page).toHaveURL(/\/home/i);
    await attachEvidence(page, testInfo, 'post-login-home');
  });

  test('TC-BF-LOGIN-001-N01 invalid credentials remain on login @regression', async ({ loginPage, page }) => {
    await loginPage.goto();
    await loginPage.login('invalid_user_xyz', 'invalid_pass_xyz');
    await expect(page).toHaveURL(/login/i);
  });

  test('TC-BF-LOGIN-001-E01 empty credentials do not authenticate @regression', async ({ loginPage, page }) => {
    await loginPage.goto();
    await loginPage.login('', '');
    await expect(page).toHaveURL(/login/i);
  });
});
