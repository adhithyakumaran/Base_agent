import { chromium, type Browser, type BrowserContext } from '@playwright/test';

const STEALTH_ARGS = ['--disable-blink-features=AutomationControlled'];

const DEFAULT_USER_AGENT =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

export async function launchUatBrowser(headless: boolean): Promise<Browser> {
  const launchOptions = {
    headless,
    args: STEALTH_ARGS,
  };

  if (process.env.EA_USE_SYSTEM_CHROME !== 'false') {
    const channel = process.env.EA_BROWSER_CHANNEL ?? 'chrome';
    try {
      return await chromium.launch({ ...launchOptions, channel });
    } catch (error) {
      console.warn(
        `System Chrome unavailable (${error instanceof Error ? error.message : error}); using bundled Chromium`
      );
    }
  }

  return chromium.launch(launchOptions);
}

export async function newUatContext(browser: Browser, baseURL: string): Promise<BrowserContext> {
  const context = await browser.newContext({
    baseURL,
    ignoreHTTPSErrors: process.env.EA_IGNORE_HTTPS_ERRORS === 'true',
    userAgent: process.env.EA_USER_AGENT ?? DEFAULT_USER_AGENT,
    viewport: { width: 1366, height: 768 },
    locale: 'en-US',
  });

  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  });

  return context;
}
