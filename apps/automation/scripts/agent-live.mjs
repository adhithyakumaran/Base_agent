#!/usr/bin/env node
/**
 * Live demo agent run — forwards goal to orchestrator with LIVE_DEMO browser env.
 * Usage: npm run agent:live -- "Search SKU ABC123"
 */
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const goal = process.argv.slice(2).join(' ').trim();
if (!goal) {
  console.error('Usage: npm run agent:live -- "<goal>"');
  process.exit(2);
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..', '..', '..');

const env = {
  ...process.env,
  QA_RUN_MODE: 'LIVE_DEMO',
  QA_LIVE_BROWSER: 'true',
  QA_BROWSER_HEADLESS: 'false',
  QA_KEEP_BROWSER_OPEN: 'true',
  QA_BROWSER_CHANNEL: process.env.QA_BROWSER_CHANNEL || 'chrome',
  QA_LIVE_ACTION_DELAY_MS: process.env.QA_LIVE_ACTION_DELAY_MS || '500',
  QA_RUNNER: 'playwright',
  QA_AUTOMATION_DIR: path.join(root, 'apps', 'automation'),
};

const py = process.platform === 'win32' ? 'python' : 'python3';
const result = spawnSync(
  py,
  ['-m', 'qa_orchestrator.api', goal, '--type', 'adhoc'],
  {
    cwd: root,
    env: {
      ...env,
      PYTHONPATH: [
        path.join(root, 'services', 'qa-orchestrator'),
        path.join(root, 'services', 'agent-runtime'),
        root,
      ].join(path.delimiter),
    },
    stdio: 'inherit',
  }
);

process.exit(result.status ?? 1);
