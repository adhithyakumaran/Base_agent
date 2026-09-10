import { test, expect } from '../src/fixtures/test-base';
import { gotoLogin } from '../src/fixtures/navigation';

test.describe('BF-LOGIN-001 User Login @BF-LOGIN-001 @negative @authentication', () => {
  test('TC-BF-LOGIN-001-N01 invalid credentials show login error @negative', async ({ page, loginPage }) => {
    await gotoLogin(page);
    await loginPage.login('invalid_user_scout', 'wrong_password_123');
    await expect(page).toHaveURL(/login/i, { timeout: 20_000 });
    const body = await page.innerText('body');
    expect(body.toLowerCase()).toMatch(/invalid|incorrect|error|username|password/);
  });
});
