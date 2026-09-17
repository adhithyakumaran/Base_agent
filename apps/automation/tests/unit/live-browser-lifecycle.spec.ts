import fs from 'fs';
import os from 'os';
import path from 'path';
import { test, expect } from '@playwright/test';
import { resetLiveBrowserClosedForTests } from '../../src/core/live-browser-lifecycle';
import {
  getSharedLiveContext,
  resetLiveBrowserSharedForTests,
  setSharedLiveContext,
} from '../../src/core/live-browser-shared';

test.describe('live browser lifecycle', () => {
  test.afterEach(() => {
    resetLiveBrowserClosedForTests();
    resetLiveBrowserSharedForTests();
  });

  test('shared context registry reuses profile key', async () => {
    expect(getSharedLiveContext()).toBeNull();
    const fake = { pages: () => [] } as unknown as import('@playwright/test').BrowserContext;
    process.env.QA_LIVE_PROFILE_DIR = path.join(os.tmpdir(), 'scout-live-test-profile');
    setSharedLiveContext(fake);
    expect(getSharedLiveContext()).toBe(fake);
    resetLiveBrowserSharedForTests();
    expect(getSharedLiveContext()).toBeNull();
  });

  test('keeper script exists for QA_KEEP_BROWSER_OPEN close contract', async () => {
    const keeper = path.resolve(__dirname, '../../../scripts/live-browser-keeper.mjs');
    expect(fs.existsSync(keeper)).toBeTruthy();
  });
});
