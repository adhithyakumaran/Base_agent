import { test, expect } from '../../src/fixtures/test-base';

const ADMIN_FUNCTIONS = [
  'App Configuration',
  'Maintain Item Size',
  'Maintain Users',
  'Dashboard',
  'Access Control',
];

test.describe('BF-ADMINISTRATION-009 Administration @BF-ADMINISTRATION-009 @regression @read-only-sanity @no-data-mutation', () => {
  test('TC-BF-ADMINISTRATION-009-P01 administration master loads @sanity', async ({ page }) => {
    await page.goto('/administration');
    await expect(page.locator('body')).toBeVisible();
  });

  for (const fn of ADMIN_FUNCTIONS) {
    test(`TC-BF-ADMINISTRATION-009-P0x ${fn} entry visible @regression`, async ({ page }) => {
      await page.goto('/administration');
      await expect(page.locator(`text=${fn}`).first()).toBeVisible({ timeout: 15_000 });
    });
  }
});
