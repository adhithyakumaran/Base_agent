import { test, expect } from '../../src/fixtures/test-base';
import { assertNoDestructiveAction } from '../../src/core/safety-guardrails';

const REPORTS: Array<{ name: string; path: string }> = [
  { name: 'Order Status', path: '/ea1/29' },
  { name: 'Logged in Users', path: '/ea1/101' },
  { name: 'TryOn Usage', path: '/ea1/55' },
  { name: 'Manual Bill Report', path: '/ea1/manual-bill-report' },
  { name: 'QMS Report', path: '/qms-report' },
];

test.describe('BF-REPORTS-007 Reports @BF-REPORTS-007 @regression @read-only-sanity @no-transaction', () => {
  test.beforeEach(() => {
    assertNoDestructiveAction('delete report', 'BF-REPORTS-007');
  });

  test('TC-BF-REPORTS-007-P01 reports master page loads @sanity', async ({ page }) => {
    await page.goto('/ea1/51');
    await expect(page.locator('body')).toBeVisible();
  });

  for (const report of REPORTS) {
    test(`TC-BF-REPORTS-007-P0x ${report.name} page loads @regression`, async ({ page }) => {
      await page.goto(report.path);
      await expect(page.locator('body')).toBeVisible();
    });
  }
});
