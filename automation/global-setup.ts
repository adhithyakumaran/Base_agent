import { chromium, type FullConfig } from '@playwright/test';
import dotenv from 'dotenv';
import path from 'path';

dotenv.config({ path: path.resolve(__dirname, 'config', '.env') });

async function globalSetup(config: FullConfig): Promise<void> {
  const baseURL = config.projects[0]?.use?.baseURL as string;
  const user = process.env.EA_USER_USERNAME;
  const pass = process.env.EA_USER_PASSWORD;
  if (!user || !pass) {
    console.warn('Skipping auth storage — EA_USER_USERNAME/PASSWORD not set');
    return;
  }

  const browser = await chromium.launch();
  const page = await browser.newPage({ baseURL });
  const loginPath = process.env.EA_LOGIN_URL ?? '/login';
  await page.goto(loginPath);
  await page.locator('#P9999_USERNAME, input[name="P9999_USERNAME"]').first().fill(user);
  await page.locator('#P9999_PASSWORD, input[name="P9999_PASSWORD"]').first().fill(pass);
  await page.locator('#login-btn, button#login-btn').first().click();
  await page.waitForURL(/\/home/i, { timeout: 60_000 });
  await page.context().storageState({ path: path.resolve(__dirname, '.auth', 'user.json') });
  await browser.close();
}

export default globalSetup;
