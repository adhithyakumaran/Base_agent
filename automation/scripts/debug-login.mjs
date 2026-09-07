import { chromium } from '@playwright/test';
import dotenv from 'dotenv';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

dotenv.config({ path: path.join(ROOT, 'config', '.env') });

const USERNAME_SELECTORS = [
  '#P9999_USERNAME',
  'input[name="P9999_USERNAME"]',
  'input[placeholder="Username"]',
];
const PASSWORD_SELECTORS = [
  '#P9999_PASSWORD',
  'input[name="P9999_PASSWORD"]',
  'input[autocomplete="current-password"]',
];
const SUBMIT_SELECTORS = ['#login-btn', 'button#login-btn', 'button:has-text("Login")'];

function normalizeBaseUrl(raw) {
  const fallback = 'https://uat.example.com/ords/r/tjdcom/ea';
  if (!raw) return fallback;
  let url = raw.trim().replace(/\/+$/, '');
  return url.replace(/\/login\/?$/i, '');
}

function toAppRelativePath(pathSegment, fallback) {
  const raw = (pathSegment ?? fallback).trim();
  if (/^https?:\/\//i.test(raw)) return raw;
  return raw.replace(/^\/+/, '');
}

function resolveAppUrl(baseURL, pathSegment, fallback) {
  const segment = toAppRelativePath(pathSegment, fallback);
  if (/^https?:\/\//i.test(segment)) return segment;
  return `${normalizeBaseUrl(baseURL)}/${segment}`;
}

async function findLoginScope(page) {
  for (const selector of USERNAME_SELECTORS) {
    if ((await page.locator(selector).count()) > 0) return page;
  }
  for (const frame of page.frames()) {
    if (frame === page.mainFrame()) continue;
    for (const selector of USERNAME_SELECTORS) {
      if ((await frame.locator(selector).count()) > 0) return frame;
    }
  }
  return page;
}

async function firstVisible(page, scope, selectors, timeoutMs = 60_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    for (const selector of selectors) {
      const locator = scope.locator(selector).first();
      if ((await locator.count()) > 0 && (await locator.isVisible().catch(() => false))) {
        return locator;
      }
    }
    await page.waitForTimeout(250);
  }
  throw new Error(`No visible control for selectors: ${selectors.join(', ')}`);
}

async function dumpFailure(page, reason) {
  const reportsDir = path.join(ROOT, 'reports');
  fs.mkdirSync(reportsDir, { recursive: true });
  const screenshotPath = path.join(reportsDir, 'debug-login-failure.png');
  const htmlPath = path.join(reportsDir, 'debug-login-failure.html');
  await page.screenshot({ path: screenshotPath, fullPage: true }).catch(() => undefined);
  fs.writeFileSync(htmlPath, await page.content().catch(() => '<unavailable>'), 'utf8');
  const inputs = await page.locator('input').count().catch(() => -1);
  console.error([
    reason,
    `url=${page.url()}`,
    `title=${await page.title().catch(() => 'unknown')}`,
    `inputs=${inputs}`,
    `frames=${page.frames().length}`,
    `screenshot=${screenshotPath}`,
    `html=${htmlPath}`,
  ].join('\n'));
}

async function main() {
  const baseURL = normalizeBaseUrl(process.env.EA_BASE_URL);
  const user = process.env.EA_USER_USERNAME;
  const pass = process.env.EA_USER_PASSWORD;
  const login = toAppRelativePath(process.env.EA_LOGIN_URL, 'login');
  const loginUrl = resolveAppUrl(baseURL, process.env.EA_LOGIN_URL, 'login');
  const headless = process.env.EA_HEADLESS === 'true';

  console.log(`Debug login: ${loginUrl}`);
  console.log(`headless=${headless}, user=${user ? '[set]' : '[missing]'}`);

  const browser = await chromium.launch({
    headless,
    slowMo: headless ? 0 : 300,
    channel: process.env.EA_USE_SYSTEM_CHROME === 'false' ? undefined : (process.env.EA_BROWSER_CHANNEL ?? 'chrome'),
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const context = await browser.newContext({
    baseURL,
    ignoreHTTPSErrors: process.env.EA_IGNORE_HTTPS_ERRORS === 'true',
    userAgent:
      process.env.EA_USER_AGENT ??
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    viewport: { width: 1366, height: 768 },
  });
  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  });
  const page = await context.newPage();

  try {
    await page.goto(login, { waitUntil: 'load', timeout: 90_000 });
    console.log('Loaded URL:', page.url());
    console.log('Title:', await page.title());

    const scope = await findLoginScope(page);
    const username = await firstVisible(page, scope, USERNAME_SELECTORS);
    console.log('Username field found');

    if (user && pass) {
      await username.fill(user);
      await (await firstVisible(page, scope, PASSWORD_SELECTORS, 15_000)).fill(pass);
      await (await firstVisible(page, scope, SUBMIT_SELECTORS, 15_000)).click();
      await page.waitForURL(/\/home/i, { timeout: 90_000 });
      console.log('Login succeeded:', page.url());
    } else {
      console.log('EA_USER_USERNAME/PASSWORD not set — skipped submit');
    }
  } catch (error) {
    await dumpFailure(page, error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  } finally {
    if (!headless) {
      console.log('Browser stays open for 15s so you can inspect the page…');
      await page.waitForTimeout(15_000);
    }
    await browser.close();
  }
}

main();
