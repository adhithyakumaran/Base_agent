import type { Frame, Page } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { LOCATORS } from './locator-chain';

export function normalizeBaseUrl(raw: string | undefined): string {
  const fallback = 'https://uat.example.com/ords/r/tjdcom/ea';
  if (!raw) return fallback;
  let url = raw.trim().replace(/\/+$/, '');
  url = url.replace(/\/login\/?$/i, '');
  return url;
}

async function countMatchingInputs(scope: Page | Frame, selectors: readonly string[]): Promise<number> {
  let total = 0;
  for (const selector of selectors) {
    total += await scope.locator(selector).count();
  }
  return total;
}

export async function findLoginScope(page: Page): Promise<Page | Frame> {
  for (const selector of LOCATORS.login.username) {
    if ((await page.locator(selector).count()) > 0) return page;
  }
  for (const frame of page.frames()) {
    if (frame === page.mainFrame()) continue;
    for (const selector of LOCATORS.login.username) {
      if ((await frame.locator(selector).count()) > 0) return frame;
    }
  }
  return page;
}

export async function waitForLoginForm(page: Page, timeoutMs = 60_000): Promise<Page | Frame> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const scope = await findLoginScope(page);
    for (const selector of LOCATORS.login.username) {
      const locator = scope.locator(selector).first();
      if ((await locator.count()) > 0 && (await locator.isVisible().catch(() => false))) {
        return scope;
      }
    }
    await page.waitForTimeout(250);
  }
  throw new Error('Login form did not become visible before timeout');
}

export async function fillLoginForm(
  scope: Page | Frame,
  user: string,
  pass: string
): Promise<void> {
  let filledUser = false;
  for (const selector of LOCATORS.login.username) {
    const locator = scope.locator(selector).first();
    if ((await locator.count()) > 0) {
      await locator.fill(user, { timeout: 15_000 });
      filledUser = true;
      break;
    }
  }
  if (!filledUser) throw new Error('Username field not found');

  let filledPass = false;
  for (const selector of LOCATORS.login.password) {
    const locator = scope.locator(selector).first();
    if ((await locator.count()) > 0) {
      await locator.fill(pass, { timeout: 15_000 });
      filledPass = true;
      break;
    }
  }
  if (!filledPass) throw new Error('Password field not found');

  for (const selector of LOCATORS.login.submit) {
    const locator = scope.locator(selector).first();
    if ((await locator.count()) > 0) {
      await locator.click({ timeout: 15_000 });
      return;
    }
  }
  throw new Error('Login submit control not found');
}

export async function dumpLoginFailure(page: Page, reportsDir: string, reason: string): Promise<string> {
  fs.mkdirSync(reportsDir, { recursive: true });
  const screenshotPath = path.join(reportsDir, 'global-setup-failure.png');
  const htmlPath = path.join(reportsDir, 'global-setup-failure.html');
  await page.screenshot({ path: screenshotPath, fullPage: true }).catch(() => undefined);
  const html = await page.content().catch(() => '<unavailable>');
  fs.writeFileSync(htmlPath, html, 'utf8');

  const title = await page.title().catch(() => 'unknown');
  const inputCount = await page.locator('input').count().catch(() => -1);
  const frameCount = page.frames().length;
  const usernameMatches = await countMatchingInputs(page, LOCATORS.login.username);
  const blockedByWaf = /not acceptable|406|blocked due to suspicious/i.test(`${title}\n${html}`);

  return [
    reason,
    `url=${page.url()}`,
    `title=${title}`,
    `inputs=${inputCount}`,
    `frames=${frameCount}`,
    `username_locator_matches=${usernameMatches}`,
    blockedByWaf ? 'detected=WAF_BLOCK (AppTrana/406 — use EA_USE_SYSTEM_CHROME=true and EA_HEADLESS=false)' : '',
    `screenshot=${screenshotPath}`,
    `html=${htmlPath}`,
    'Tips: open the URL in Chrome, confirm VPN, try EA_HEADLESS=false, set EA_USE_SYSTEM_CHROME=true.',
  ]
    .filter(Boolean)
    .join('\n');
}
