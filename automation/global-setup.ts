import { chromium, type FullConfig } from '@playwright/test';
import dotenv from 'dotenv';
import path from 'path';

dotenv.config({ path: path.resolve(__dirname, 'config', '.env') });

function normalizeBaseUrl(raw: string | undefined): string {
  const fallback = 'https://uat.example.com/ords/r/tjdcom/ea';
  if (!raw) return fallback;
  let url = raw.trim().replace(/\/+$/, '');
  // Common misconfig: full login URL pasted into EA_BASE_URL
  url = url.replace(/\/login\/?$/i, '');
  return url;
}

async function globalSetup(config: FullConfig): Promise<void> {
  const baseURL = normalizeBaseUrl(
    process.env.EA_BASE_URL ?? (config.projects[0]?.use?.baseURL as string)
  );
  const user = process.env.EA_USER_USERNAME;
  const pass = process.env.EA_USER_PASSWORD;
  if (!user || !pass) {
    console.warn('Skipping auth storage — EA_USER_USERNAME/PASSWORD not set');
    return;
  }

  const browser = await chromium.launch({ headless: process.env.EA_HEADLESS !== 'false' });
  const page = await browser.newPage({ baseURL });
  const loginPath = process.env.EA_LOGIN_URL ?? '/login';
  console.log(`Global setup: login ${baseURL}${loginPath} as ${user}`);
  await page.goto(loginPath, { waitUntil: 'domcontentloaded', timeout: 60_000 });
  await page.locator('#P9999_USERNAME, input[name="P9999_USERNAME"]').first().fill(user, { timeout: 45_000 });
  await page.locator('#P9999_PASSWORD, input[name="P9999_PASSWORD"]').first().fill(pass);
  await page.locator('#login-btn, button#login-btn, button:has-text("Login")').first().click();
  await page.waitForURL(/\/home/i, { timeout: 60_000 });
  await page.context().storageState({ path: path.resolve(__dirname, '.auth', 'user.json') });
  await browser.close();
}

export default globalSetup;
