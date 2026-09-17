#!/usr/bin/env node
/** Validate a generated draft spec via Playwright test discovery (no UAT execution). */
import { spawnSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const rel = process.argv[2];
const expectedFlowId = process.argv[3];
const expectedTestCaseId = process.argv[4];

if (!rel) {
  console.log(JSON.stringify({ ok: false, error: 'usage: validate-generated-spec.mjs <relative-spec-path> [flowId] [testCaseId]' }));
  process.exit(1);
}

const automationDir = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const specPath = path.resolve(automationDir, rel);
if (!specPath.includes(path.join('generated', 'drafts'))) {
  console.log(JSON.stringify({ ok: false, error: 'spec must live under generated/drafts' }));
  process.exit(1);
}

const content = fs.readFileSync(specPath, 'utf8');
const configPath = path.join(automationDir, 'playwright.drafts.config.ts');
const configArg = fs.existsSync(configPath) ? ['--config=playwright.drafts.config.ts'] : [];

const result = spawnSync(
  'npx',
  ['playwright', 'test', rel, '--list', ...configArg],
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

const listed = (result.stdout || '').trim();
const tags = {
  flow_id: expectedFlowId && content.includes(expectedFlowId),
  test_case_id: expectedTestCaseId && content.includes(expectedTestCaseId),
  generated: content.includes('@generated'),
  draft: content.includes('@draft'),
  listed: /^\s*\[/.test(listed) || /Total:\s*[1-9]/i.test(listed),
};

if (expectedFlowId && !tags.flow_id) {
  console.log(JSON.stringify({ ok: false, error: `missing flow tag ${expectedFlowId}` }));
  process.exit(1);
}
if (expectedTestCaseId && !tags.test_case_id) {
  console.log(JSON.stringify({ ok: false, error: `missing test case id ${expectedTestCaseId}` }));
  process.exit(1);
}
if (!tags.generated || !tags.draft) {
  console.log(JSON.stringify({ ok: false, error: 'missing @generated or @draft tag' }));
  process.exit(1);
}
if (!tags.listed) {
  console.log(JSON.stringify({ ok: false, error: 'test not discovered by playwright --list', output: listed.slice(0, 300) }));
  process.exit(1);
}

console.log(
  JSON.stringify({
    ok: true,
    listed: true,
    tags,
    output: listed.slice(0, 300),
  })
);
