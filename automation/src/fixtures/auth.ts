import type { Page } from '@playwright/test';
import path from 'path';
import { dismissBlockingOverlays } from '../core/apex-overlays';
import { homeUrl, loginUrl } from '../core/app-url';
import { performLogin } from '../core/login-setup';

const AUTH_FILE = path.resolve(__dirname, '../../.auth/user.json');

/** Navigate to home; re-login when session expired or invalidated (e.g. after BF-LOGOUT-002). */
export async function ensureAuthenticated(page: Page): Promise<void> {
  await dismissBlockingOverlays(page);
  await page.goto(homeUrl(), { waitUntil: 'domcontentloaded', timeout: 60_000 });
  if (/\/home/i.test(page.url())) {
    await dismissBlockingOverlays(page);
    await page.locator('a.custom-card-wrap, .t-Body-content').first().waitFor({ state: 'visible', timeout: 20_000 }).catch(() => undefined);
    return;
  }

  const user = process.env.EA_USER_USERNAME;
  const pass = process.env.EA_USER_PASSWORD;
  if (!user || !pass) {
    throw new Error('EA_USER_USERNAME and EA_USER_PASSWORD must be set in automation/config/.env');
  }

  await dismissBlockingOverlays(page);

  if (!/\/login/i.test(page.url())) {
    await page.goto(loginUrl(), { waitUntil: 'domcontentloaded', timeout: 60_000 });
  }

  await dismissBlockingOverlays(page);
  await performLogin(page, user, pass);
  if (!/\/home/i.test(page.url())) {
    throw new Error(`Authentication failed — landed on ${page.url()}`);
  }

  await page.context().storageState({ path: AUTH_FILE }).catch(() => undefined);
}

export async function refreshAuthStorage(page: Page): Promise<void> {
  await page.context().storageState({ path: AUTH_FILE });
}
