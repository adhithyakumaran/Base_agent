#!/usr/bin/env node
/**
 * Canonical single-flow runner — positive or negative only.
 * Usage: node scripts/run-flow.mjs positive BF-LOGIN-001
 */
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildFlowGrep, normalizeFlowId } from './run-flow-grep.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');

const [polarity, rawFlowId] = process.argv.slice(2);
if (!polarity || !rawFlowId) {
  console.error('Usage: node scripts/run-flow.mjs <positive|negative> <BF-FLOW-ID>');
  process.exit(2);
}

let flowId;
try {
  flowId = normalizeFlowId(rawFlowId);
} catch (err) {
  console.error(err.message);
  process.exit(2);
}

const playwrightArgs = ['playwright', 'test', '--grep', buildFlowGrep(polarity, flowId)];

const result = spawnSync('npx', playwrightArgs, {
  cwd: root,
  stdio: 'inherit',
  env: process.env,
  shell: process.platform === 'win32',
});

process.exit(result.status ?? 1);
