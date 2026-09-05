import { defineConfig, devices } from '@playwright/test';
import dotenv from 'dotenv';
import path from 'path';

dotenv.config({ path: path.resolve(__dirname, 'config', '.env') });
dotenv.config({ path: path.resolve(__dirname, 'config', '.env.local'), override: true });

const baseURL = process.env.EA_BASE_URL ?? 'https://uat.example.com/ords/r/tjdcom/ea';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : 1,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: [
    ['list'],
    ['html', { outputFolder: 'reports/html', open: 'never' }],
    ['json', { outputFile: 'reports/results.json' }],
    ['junit', { outputFile: 'reports/junit.xml' }],
  ],
  outputDir: 'reports/test-results',
  globalSetup: require.resolve('./global-setup'),
  use: {
    baseURL,
    storageState: process.env.EA_USER_USERNAME ? '.auth/user.json' : undefined,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 20_000,
    navigationTimeout: 45_000,
    ignoreHTTPSErrors: process.env.EA_IGNORE_HTTPS_ERRORS === 'true',
  },
  projects: [
    {
      name: 'chromium-uat',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
