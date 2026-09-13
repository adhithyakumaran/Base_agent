#!/usr/bin/env node
/**
 * Canonical single-flow runner — positive or negative only.
 * Usage: node scripts/run-flow.mjs positive BF-LOGIN-001
 */
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');

const [polarity, rawFlowId] = process.argv.slice(2);
if (!polarity || !rawFlowId) {
  console.error('Usage: node scripts/run-flow.mjs <positive|negative> <BF-FLOW-ID>');
  process.exit(2);
}

const flowId = rawFlowId.replace(/^@/, '');
if (!/^BF-[A-Z0-9-]+$/.test(flowId)) {
  console.error(`Invalid flow id: ${rawFlowId}`);
  process.exit(2);
}

const flowTag = `@${flowId}`;
const playwrightArgs = ['playwright', 'test'];

if (polarity === 'positive') {
  playwrightArgs.push('--grep', `(?=.*${flowTag})(?=.*@positive)`);
} else if (polarity === 'negative') {
  playwrightArgs.push('--grep', `(?=.*${flowTag})(?=.*@negative)`);
} else {
  console.error(`Unknown polarity: ${polarity}`);
  process.exit(2);
}

const result = spawnSync('npx', playwrightArgs, {
  cwd: root,
  stdio: 'inherit',
  env: process.env,
  shell: process.platform === 'win32',
});

process.exit(result.status ?? 1);
