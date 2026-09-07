import type { Page } from '@playwright/test';
import path from 'path';
import { homeUrl, loginUrl } from '../core/app-url';
import { performLogin } from '../core/login-setup';

const AUTH_FILE = path.resolve(__dirname, '../../.auth/user.json');

/** Navigate to home; re-login when session expired or invalidated (e.g. after BF-LOGIN-001). */
export async function ensureAuthenticated(page: Page): Promise<void> {
  await page.goto(homeUrl(), { waitUntil: 'domcontentloaded', timeout: 60_000 });
  if (/\/home/i.test(page.url())) return;

  const user = process.env.EA_USER_USERNAME;
  const pass = process.env.EA_USER_PASSWORD;
  if (!user || !pass) {
    throw new Error('EA_USER_USERNAME and EA_USER_PASSWORD must be set in automation/config/.env');
  }

  if (!/\/login/i.test(page.url())) {
    await page.goto(loginUrl(), { waitUntil: 'domcontentloaded', timeout: 60_000 });
  }

  await performLogin(page, user, pass);
  if (!/\/home/i.test(page.url())) {
    throw new Error(`Authentication failed — landed on ${page.url()}`);
  }

  await page.context().storageState({ path: AUTH_FILE }).catch(() => undefined);
}

export async function refreshAuthStorage(page: Page): Promise<void> {
  await page.context().storageState({ path: AUTH_FILE });
}
