import baseConfig from './playwright.config';

/** Draft validation only — discovers generated specs without touching approved tests/. */
export default {
  ...baseConfig,
  testDir: '.',
  testMatch: ['generated/drafts/**/*.spec.ts'],
  globalSetup: process.env.EA_SKIP_GLOBAL_SETUP === 'true' ? undefined : baseConfig.globalSetup,
};
