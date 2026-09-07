import type { Frame, Page } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { dismissBlockingOverlays } from './apex-overlays';
import { normalizeBaseUrl } from './app-url';
import { LOCATORS } from './locator-chain';

export { normalizeBaseUrl } from './app-url';

const APEX_USERNAME = '#P9999_USERNAME';
const APEX_PASSWORD = '#P9999_PASSWORD';
const APEX_SUBMIT = '#login-btn';
const HOME_URL = /\/home/i;

function pageOf(scope: Page | Frame): Page {
  return 'page' in scope ? scope.page() : scope;
}

async function countMatchingInputs(scope: Page | Frame, selectors: readonly string[]): Promise<number> {
  let total = 0;
  for (const selector of selectors) {
    total += await scope.locator(selector).count();
  }
  return total;
}

export async function findLoginScope(page: Page): Promise<Page | Frame> {
  if ((await page.locator(APEX_USERNAME).count()) > 0) return page;
  for (const selector of LOCATORS.login.username) {
    if ((await page.locator(selector).count()) > 0) return page;
  }
  for (const frame of page.frames()) {
    if (frame === page.mainFrame()) continue;
    if ((await frame.locator(APEX_USERNAME).count()) > 0) return frame;
  }
  return page;
}

export async function waitForLoginForm(page: Page, timeoutMs = 60_000): Promise<Page | Frame> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const scope = await findLoginScope(page);
    const user = scope.locator(APEX_USERNAME);
    const submit = scope.locator(APEX_SUBMIT);
    const userReady =
      (await user.count()) > 0 &&
      ((await user.isVisible().catch(() => false)) || (await user.count()) > 0);
    const submitReady = (await submit.count()) > 0 && (await submit.isVisible().catch(() => false));
    if (userReady && submitReady) return scope;
    await page.waitForTimeout(250);
  }
  throw new Error('Login form did not become visible before timeout');
}

/** Fill an APEX item and fire input/change so custom skins + apex validation see the value. */
async function fillApexInput(scope: Page | Frame, selector: string, value: string): Promise<boolean> {
  const locator = scope.locator(selector).first();
  if ((await locator.count()) === 0) return false;

  await locator.waitFor({ state: 'attached', timeout: 15_000 });
  await locator.click({ force: true, timeout: 5_000 }).catch(() => undefined);
  await locator.fill('', { force: true }).catch(() => undefined);
  await locator.pressSequentially(value, { delay: 40 });

  const current = await locator.inputValue().catch(() => '');
  if (current !== value) {
    await locator.evaluate(
      (el, v) => {
        const input = el as HTMLInputElement;
        input.value = v;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      },
      value
    );
  }
  return true;
}

async function fillWithFallbacks(
  scope: Page | Frame,
  selectors: readonly string[],
  value: string,
  label: 'username' | 'password'
): Promise<void> {
  const apexSelector = label === 'username' ? APEX_USERNAME : APEX_PASSWORD;
  if (await fillApexInput(scope, apexSelector, value)) return;

  for (const selector of selectors) {
    if (selector === APEX_USERNAME || selector === APEX_PASSWORD) continue;
    const locator = scope.locator(selector).first();
    if ((await locator.count()) === 0) continue;
    if (!(await locator.isVisible().catch(() => false))) continue;
    await locator.click();
    await locator.fill(value);
    return;
  }
  throw new Error(`${label} field not found`);
}

export async function fillLoginForm(scope: Page | Frame, user: string, pass: string): Promise<void> {
  await fillWithFallbacks(scope, LOCATORS.login.username, user, 'username');
  await fillWithFallbacks(scope, LOCATORS.login.password, pass, 'password');
  await pageOf(scope).waitForTimeout(300);
  await submitLogin(scope);
}

async function submitLogin(scope: Page | Frame): Promise<void> {
  const page = pageOf(scope);

  if (HOME_URL.test(page.url())) return;

  const btn = scope.locator(APEX_SUBMIT).first();
  const pass = scope.locator(APEX_PASSWORD).first();

  for (let attempt = 0; attempt < 3; attempt++) {
    await dismissBlockingOverlays(page);

    // 1) Enter on password — works even when ui-widget-overlay blocks the LOGIN button
    if ((await pass.count()) > 0) {
      await Promise.all([
        page.waitForURL(HOME_URL, { timeout: 45_000, waitUntil: 'domcontentloaded' }).catch(() => null),
        pass.press('Enter'),
      ]);
      if (HOME_URL.test(page.url())) return;
    }

    await dismissBlockingOverlays(page);

    // 2) APEX programmatic submit
    await page
      .evaluate(() => {
        const w = window as typeof window & {
          apex?: { submit?: (label: string) => void; page?: { submit?: (label: string) => void } };
        };
        if (w.apex?.page?.submit) w.apex.page.submit('LOGIN');
        else if (w.apex?.submit) w.apex.submit('LOGIN');
      })
      .catch(() => undefined);
    await page.waitForURL(HOME_URL, { timeout: 30_000, waitUntil: 'domcontentloaded' }).catch(() => null);
    if (HOME_URL.test(page.url())) return;

    if ((await btn.count()) === 0) {
      throw new Error('Login submit control #login-btn not found');
    }

    await btn.scrollIntoViewIfNeeded();

    // 3) Force click through any remaining overlay
    await Promise.all([
      page.waitForURL(HOME_URL, { timeout: 30_000, waitUntil: 'domcontentloaded' }).catch(() => null),
      btn.click({ force: true, timeout: 15_000 }),
    ]);
    if (HOME_URL.test(page.url())) return;

    // 4) DOM click fallback
    await btn.evaluate((el: HTMLElement) => el.click());
    await page.waitForURL(HOME_URL, { timeout: 30_000, waitUntil: 'domcontentloaded' }).catch(() => null);
    if (HOME_URL.test(page.url())) return;
  }

  if (!HOME_URL.test(page.url())) {
    const errText = await page
      .locator('.t-Alert, .a-Alert, .u-visible, [role="alert"]')
      .allTextContents()
      .catch(() => []);
    const hint = errText.filter(Boolean).join(' ').trim();
    throw new Error(
      hint
        ? `Login did not reach /home — ${hint}`
        : 'Login did not reach /home — submit fired but credentials may be wrong or session blocked'
    );
  }
}

export async function performLogin(page: Page, user: string, pass: string): Promise<void> {
  await dismissBlockingOverlays(page);
  await waitForLoginForm(page);
  const scope = await findLoginScope(page);
  await fillLoginForm(scope, user, pass);
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
  const userValue = await page.locator(APEX_USERNAME).inputValue().catch(() => '[unreadable]');
  const blockedByWaf = /not acceptable|406|blocked due to suspicious/i.test(`${title}\n${html}`);
  const wrongRootPath =
    (/404|not found|isn't available/i.test(`${title}\n${html}`) &&
      !page.url().includes('/ords/r/tjdcom/ea/')) ||
    /\/tjdcom\/login\b/i.test(page.url());

  return [
    reason,
    `url=${page.url()}`,
    `title=${title}`,
    `inputs=${inputCount}`,
    `frames=${frameCount}`,
    `username_locator_matches=${usernameMatches}`,
    `P9999_USERNAME_value=${userValue ? '[set]' : '[empty]'}`,
    blockedByWaf ? 'detected=WAF_BLOCK (AppTrana/406 — use EA_USE_SYSTEM_CHROME=true and EA_HEADLESS=false)' : '',
    wrongRootPath
      ? 'detected=WRONG_URL (use EA_LOGIN_URL=login without leading slash, or git pull latest fix)'
      : '',
    `screenshot=${screenshotPath}`,
    `html=${htmlPath}`,
    'Tips: verify password in automation/config/.env, try manual login in same browser.',
  ]
    .filter(Boolean)
    .join('\n');
}
