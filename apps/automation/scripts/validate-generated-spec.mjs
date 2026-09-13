#!/usr/bin/env node
/** Validate a generated draft spec via Playwright test discovery (no UAT execution). */
import { spawnSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const rel = process.argv[2];
if (!rel) {
  console.log(JSON.stringify({ ok: false, error: 'usage: validate-generated-spec.mjs <relative-spec-path>' }));
  process.exit(1);
}

const automationDir = path.dirname(path.dirname(new URL(import.meta.url).pathname));
const specPath = path.resolve(automationDir, rel);
if (!specPath.includes(path.join('generated', 'drafts'))) {
  console.log(JSON.stringify({ ok: false, error: 'spec must live under generated/drafts' }));
  process.exit(1);
}

const result = spawnSync(
  'npx',
  ['playwright', 'test', rel, '--list'],
  { cwd: automationDir, encoding: 'utf8', env: { ...process.env, EA_SKIP_GLOBAL_SETUP: 'true' } }
);

if (result.status !== 0) {
  console.log(
    JSON.stringify({
      ok: false,
      error: (result.stderr || result.stdout || 'playwright test --list failed').slice(0, 500),
    })
  );
  process.exit(1);
}

console.log(JSON.stringify({ ok: true, listed: true, output: (result.stdout || '').slice(0, 300) }));
