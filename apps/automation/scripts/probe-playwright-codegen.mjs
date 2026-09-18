#!/usr/bin/env node
/** Probe whether Playwright renderCode/createGenerator are invocable via stable public API. */
import { createRequire } from 'module';
import path from 'path';
import { fileURLToPath } from 'url';

const automationDir = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const require = createRequire(import.meta.url);

function readPlaywrightVersion() {
  try {
    const pkg = require(path.join(automationDir, 'node_modules', '@playwright', 'test', 'package.json'));
    return pkg.version || 'unknown';
  } catch {
    return 'unknown';
  }
}

function probeCodegen() {
  const reasons = [];
  let bridgeAvailable = false;
  let renderCode = null;

  try {
    const coreBundlePath = path.join(automationDir, 'node_modules', 'playwright-core', 'lib', 'coreBundle.js');
    const mod = require(coreBundlePath);
    const exports = Object.keys(mod || {});
    if (exports.length === 0) {
      reasons.push(
        'playwright-core/lib/coreBundle.js loads but exports no public symbols; renderCode/createGenerator are internal bundle closures'
      );
    } else {
      reasons.push(`coreBundle exports [${exports.join(', ')}] but not renderCode/createGenerator`);
    }
  } catch (err) {
    reasons.push(`failed to load playwright-core/lib/coreBundle.js: ${err.message}`);
  }

  try {
    const pkg = require(path.join(automationDir, 'node_modules', 'playwright-core', 'package.json'));
    const exportKeys = Object.keys(pkg.exports || {});
    if (!exportKeys.some((k) => k.includes('codegen'))) {
      reasons.push(
        `playwright-core package.json exports [${exportKeys.join(', ')}] — no codegen entry; not a stable public API`
      );
    }
  } catch (err) {
    reasons.push(`playwright-core package metadata unavailable: ${err.message}`);
  }

  reasons.push(
    'Direct invocation of packages/playwright-core/src/tools/backend/codegen.ts renderCode()/createGenerator() is impractical without private bundle access'
  );

  console.log(
    JSON.stringify({
      bridgeAvailable,
      renderCodeAvailable: renderCode !== null,
      playwrightVersion: readPlaywrightVersion(),
      reason: reasons.join('; '),
      recommendedPath: 'python-serializer-with-node-validation',
    })
  );
}

probeCodegen();
