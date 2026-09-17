/**
 * Live demo fixtures — persistent Chrome profile + page objects for real headed runs.
 */
import { test as base, expect, chromium, type BrowserContext, type Page } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { captureStepEvidence, wrapPageWithEvidence } from '../core/evidence';
import { emitLiveEvent } from '../core/live-events';
import {
  noteKeepOpenBrowserLeftRunning,
  readSessionMetaFromDisk,
  spawnKeepOpenKeeper,
  writeSessionMeta,
} from '../core/live-browser-lifecycle';
import {
  getSharedLiveContext,
  getLiveRunDiagnostics,
  isLiveSessionAuthenticated,
  markLiveSessionAuthenticated,
  recordLiveBrowserLaunch,
  recordLiveContextAttach,
  recordLiveLogin,
  setSharedLiveContext,
} from '../core/live-browser-shared';
import { homeUrl, loginUrl, normalizeBaseUrl } from '../core/app-url';
import { performLogin } from '../core/login-setup';
import { ensureAuthenticated } from './auth';
import { LoginPage } from '../pages/login.page';
import { HomePage } from '../pages/home.page';
import { ProductSearchPage } from '../pages/product-search.page';
import { StockVisibilityPage } from '../pages/stock-visibility.page';

const keepOpen = () => process.env.QA_KEEP_BROWSER_OPEN === 'true';

function devToolsPort(profileDir: string): string | null {
  const portFile = path.join(profileDir, 'DevToolsActivePort');
  if (!fs.existsSync(portFile)) return null;
  const line = fs.readFileSync(portFile, 'utf8').split('\n')[0]?.trim();
  return line || null;
}

async function attachExistingLiveContext(profileDir: string): Promise<BrowserContext | null> {
  const runId = process.env.QA_RUN_ID || '';
  const meta = readSessionMetaFromDisk(profileDir);
  const port = devToolsPort(profileDir);
  if (!port) return null;
  if (meta.status !== 'ACTIVE' && meta.status !== 'STARTING') return null;
  if (meta.run_id && runId && meta.run_id !== runId) {
    throw new Error(
      'LIVE_BROWSER_STALE: Active browser on this profile belongs to another run. Use Close Browser first.'
    );
  }
  try {
    const browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
    const contexts = browser.contexts();
    const context = contexts[0];
    if (!context) return null;
    recordLiveContextAttach();
    setSharedLiveContext(context);
    writeSessionMeta({
      attached_via_cdp: true,
      run_id: runId || meta.run_id,
      diagnostics: getLiveRunDiagnostics(),
    });
    return context;
  } catch {
    return null;
  }
}

async function launchLiveContext(): Promise<BrowserContext> {
  const existing = getSharedLiveContext();
  if (existing) {
    return existing;
  }

  const profileDir =
    process.env.QA_LIVE_PROFILE_DIR || path.resolve('reports/browser-profiles/default-live');
  fs.mkdirSync(profileDir, { recursive: true });

  const attached = await attachExistingLiveContext(profileDir);
  if (attached) {
    await emitLiveEvent({
      phase: 'BROWSER',
      action: 'ATTACH',
      status: 'OK',
      value_summary: 'Reused persistent Chrome via CDP',
    });
    return attached;
  }

  const port = devToolsPort(profileDir);
  const meta = readSessionMetaFromDisk(profileDir);
  if (port && meta.keep_open && meta.status === 'ACTIVE') {
    throw new Error(
      'LIVE_BROWSER_STALE: Browser still active on this profile. Use Close Browser before launching again.'
    );
  }

  const channel = process.env.QA_BROWSER_CHANNEL || process.env.EA_BROWSER_CHANNEL || 'chrome';
  const headless = process.env.QA_BROWSER_HEADLESS === 'true';
  const slowMo = Number(process.env.QA_LIVE_ACTION_DELAY_MS || 0);
  try {
    const context = await chromium.launchPersistentContext(profileDir, {
      channel,
      headless,
      slowMo,
      args: ['--disable-blink-features=AutomationControlled'],
      viewport: { width: 1366, height: 768 },
      ignoreHTTPSErrors: process.env.EA_IGNORE_HTTPS_ERRORS === 'true',
    });
    recordLiveBrowserLaunch();
    setSharedLiveContext(context);
    writeSessionMeta({
      run_id: process.env.QA_RUN_ID || '',
      diagnostics: getLiveRunDiagnostics(),
    });
    return context;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    writeSessionMeta({ status: 'BROWSER_UNAVAILABLE', error: message });
    throw new Error(`BROWSER_UNAVAILABLE: ${message}`);
  }
}

async function ensureRunScopedLogin(context: BrowserContext): Promise<void> {
  if (isLiveSessionAuthenticated()) return;
  const baseURL = normalizeBaseUrl(process.env.EA_BASE_URL || '');
  const user = process.env.EA_USER_USERNAME;
  const pass = process.env.EA_USER_PASSWORD;
  if (!baseURL || !user || !pass) return;

  let page = context.pages()[0];
  if (!page) {
    page = await context.newPage();
  }
  await page.setViewportSize({ width: 1366, height: 768 });

  recordLiveLogin();
  if (process.env.EA_SKIP_GLOBAL_SETUP === 'true') {
    await ensureAuthenticated(page);
  } else {
    const target = loginUrl();
    await emitLiveEvent({ phase: 'NAVIGATE', action: 'OPEN', target });
    await page.goto(target, { waitUntil: 'load', timeout: 90_000 });
    await emitLiveEvent({ phase: 'LOGIN', action: 'AUTHENTICATE', value_summary: '[redacted]' });
    await performLogin(page, user, pass);
  }
  markLiveSessionAuthenticated();
  writeSessionMeta({ diagnostics: getLiveRunDiagnostics() });
  await page.bringToFront();
}

type Fixtures = {
  liveContext: BrowserContext;
  loginPage: LoginPage;
  homePage: HomePage;
  productSearchPage: ProductSearchPage;
  stockVisibilityPage: StockVisibilityPage;
  authenticatedPage: HomePage;
  recordStep: (label: string) => Promise<void>;
};

export const test = base.extend<Fixtures>({
  liveContext: [
    async ({}, use) => {
      const context = await launchLiveContext();
      await emitLiveEvent({ phase: 'BROWSER', action: 'LAUNCH', status: 'OK' });
      writeSessionMeta({
        status: 'ACTIVE',
        keep_open: keepOpen(),
        run_id: process.env.QA_RUN_ID || '',
        diagnostics: getLiveRunDiagnostics(),
      });
      await ensureRunScopedLogin(context);
      await use(context);
      writeSessionMeta({ diagnostics: getLiveRunDiagnostics() });
      if (!keepOpen()) {
        await context.close();
        setSharedLiveContext(null);
      } else {
        noteKeepOpenBrowserLeftRunning();
        spawnKeepOpenKeeper();
      }
    },
    { scope: 'worker', timeout: 30_000 },
  ],
  page: async ({ liveContext }, use, testInfo) => {
    const flowId = process.env.QA_FLOW_ID || '';
    const title = flowId ? `ScoutAI Live QA — ${flowId}` : 'ScoutAI Live QA';
    let page = liveContext.pages()[0];
    if (!page) {
      page = await liveContext.newPage();
    }
    await page.setViewportSize({ width: 1366, height: 768 });
    try {
      await page.setTitle(title);
    } catch {
      /* ignore */
    }
    wrapPageWithEvidence(page, testInfo, { liveEvents: true });
    await captureStepEvidence(page, testInfo, 'test-start');
    await use(page);
    await captureStepEvidence(page, testInfo, 'test-end');
    if (!keepOpen()) {
      await page.close();
    } else {
      await page.bringToFront();
    }
  },
  recordStep: async ({ page }, use, testInfo) => {
    await use(async (label: string) => {
      await captureStepEvidence(page, testInfo, label);
    });
  },
  loginPage: async ({ page }, use) => {
    await use(new LoginPage(page));
  },
  homePage: async ({ page }, use) => {
    await use(new HomePage(page));
  },
  productSearchPage: async ({ page }, use) => {
    await use(new ProductSearchPage(page));
  },
  stockVisibilityPage: async ({ page }, use) => {
    await use(new StockVisibilityPage(page));
  },
  authenticatedPage: async ({ page, homePage }, use) => {
    const user = process.env.EA_USER_USERNAME;
    const pass = process.env.EA_USER_PASSWORD;
    if (!user || !pass) {
      test.skip(true, 'EA_USER_USERNAME / EA_USER_PASSWORD not configured');
    }
    if (isLiveSessionAuthenticated()) {
      await page.goto(homeUrl(), { waitUntil: 'domcontentloaded', timeout: 60_000 }).catch(() => undefined);
      await expect(page).toHaveURL(/\/home/i, { timeout: 30_000 });
      await use(homePage);
      return;
    }
    await ensureAuthenticated(page);
    markLiveSessionAuthenticated();
    await expect(page).toHaveURL(/\/home/i, { timeout: 30_000 });
    await use(homePage);
  },
});

export { expect };
