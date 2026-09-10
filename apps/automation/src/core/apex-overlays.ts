import type { Page } from '@playwright/test';

/** Dismiss APEX jQuery UI dialogs, alerts, and notifications that block clicks. */
export async function dismissBlockingOverlays(page: Page): Promise<void> {
  for (let i = 0; i < 5; i++) {
    await page.keyboard.press('Escape').catch(() => undefined);
  }

  await page
    .locator(
      [
        '.ui-dialog-titlebar-close',
        '.ui-button-icon-closethick',
        '.a-Dialog-close',
        '.a-Notification-close',
        'button.a-Notification-close',
        '.t-Button--closeNotification',
        'button:has-text("OK")',
        'button:has-text("Ok")',
        'button:has-text("Close")',
        'button:has-text("Dismiss")',
      ].join(', ')
    )
    .first()
    .click({ timeout: 1500, force: true })
    .catch(() => undefined);

  await page
    .evaluate(() => {
      document.querySelectorAll('.ui-widget-overlay').forEach((el) => el.remove());
      document.querySelectorAll('.ui-dialog, .t-Dialog').forEach((el) => {
        (el as HTMLElement).style.display = 'none';
      });
      document.querySelectorAll('.a-Notification, .t-Alert, .a-Alert, .aErrMsg').forEach((el) => {
        (el as HTMLElement).style.display = 'none';
        el.remove();
      });
      document.body.classList.remove('ui-dialog-open', 't-Dialog-page--standard');
      document.body.style.overflow = '';
    })
    .catch(() => undefined);

  await page
    .locator('.ui-widget-overlay.ui-front, .a-Notification:visible')
    .first()
    .waitFor({ state: 'hidden', timeout: 2000 })
    .catch(() => undefined);

  await page.waitForTimeout(250);
}

export async function hasBlockingOverlay(page: Page): Promise<boolean> {
  const overlay = await page.locator('.ui-widget-overlay.ui-front').isVisible().catch(() => false);
  const notification = await page.locator('.a-Notification:visible, .aErrMsgTitle:visible').isVisible().catch(() => false);
  return overlay || notification;
}
