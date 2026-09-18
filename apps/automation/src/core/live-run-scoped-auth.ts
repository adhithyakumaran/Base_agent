import type { BrowserContext } from '@playwright/test';
import { emitLiveEvent } from './live-events';
import { homeUrl, loginUrl } from './app-url';
import { performLogin } from './login-setup';
import {
  getLiveRunDiagnostics,
  isLiveSessionAuthenticated,
  markLiveSessionAuthenticated,
  recordLiveLogin,
} from './live-browser-shared';
import { writeSessionMeta } from './live-browser-lifecycle';

/** LIVE_DEMO run-scoped login — direct login path (no ensureAuthenticated home round-trip). */
export async function ensureRunScopedLogin(context: BrowserContext): Promise<void> {
  if (isLiveSessionAuthenticated()) return;

  const user = process.env.EA_USER_USERNAME;
  const pass = process.env.EA_USER_PASSWORD;
  if (!user || !pass) return;

  let page = context.pages()[0];
  if (!page) {
    page = await context.newPage();
  }
  await page.setViewportSize({ width: 1366, height: 768 });

  try {
    await page.goto(homeUrl(), { waitUntil: 'domcontentloaded', timeout: 12_000 });
  } catch {
    /* may redirect to login */
  }
  if (/\/home/i.test(page.url())) {
    markLiveSessionAuthenticated();
    writeSessionMeta({ diagnostics: getLiveRunDiagnostics() });
    return;
  }

  const target = loginUrl();
  await emitLiveEvent({ phase: 'NAVIGATE', action: 'OPEN', target });
  await page.goto(target, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await emitLiveEvent({ phase: 'LOGIN', action: 'AUTHENTICATE', value_summary: '[redacted]' });
  await performLogin(page, user, pass);
  recordLiveLogin();
  markLiveSessionAuthenticated();
  writeSessionMeta({ diagnostics: getLiveRunDiagnostics() });
  await page.bringToFront();
}
