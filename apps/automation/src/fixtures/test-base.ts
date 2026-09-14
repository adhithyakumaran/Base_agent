import { test as stdTest, expect as stdExpect } from './test-base-std';
import { test as liveTest, expect as liveExpect } from './scout-live.fixture';

const live = process.env.QA_LIVE_BROWSER === 'true';

export const test = live ? liveTest : stdTest;
export const expect = live ? liveExpect : stdExpect;
export { ensureAuthenticated, refreshAuthStorage } from './auth';
export { gotoApp, gotoAppUrl, gotoHome, gotoLogin } from './navigation';
