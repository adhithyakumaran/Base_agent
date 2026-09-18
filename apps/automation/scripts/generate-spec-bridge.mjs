#!/usr/bin/env node
/**
 * Node bridge: JSON action model → Playwright-aligned TypeScript lines.
 * Attempts Playwright renderCode(); falls back to public API patterns when unavailable.
 */
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const automationDir = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const require = createRequire(import.meta.url);

function playwrightVersion() {
  try {
    return require(path.join(automationDir, 'node_modules', '@playwright', 'test', 'package.json')).version;
  } catch {
    return 'unknown';
  }
}

function probeRenderCode() {
  try {
    require(path.join(automationDir, 'node_modules', 'playwright-core', 'lib', 'coreBundle.js'));
    return {
      available: false,
      reason:
        'renderCode/createGenerator exist only inside playwright-core bundle closures and are not exported via package.json',
    };
  } catch (err) {
    return { available: false, reason: err.message };
  }
}

function renderActionLine(action) {
  switch (action.type) {
    case 'fill': {
      const loc = action.locator?.primary || 'page.locator("input")';
      const src = action.value_source || 'QA_PARAM_SKU';
      return [
        `const value = process.env.${src};`,
        `test.skip(!value, '${src} not set');`,
        `await ${loc}.fill(value!);`,
      ];
    }
    case 'click': {
      const loc = action.locator?.primary || 'page.locator("button")';
      return [`await ${loc}.click();`];
    }
    case 'page_object': {
      const method = action.page_object_method || 'expectLoaded';
      if (action.page_object === 'ProductSearchPage' && method === 'searchItemCode') {
        return [
          'const sku = process.env.QA_PARAM_SKU;',
          "test.skip(!sku, 'QA_PARAM_SKU not set');",
          'await productSearchPage.searchItemCode(sku!);',
        ];
      }
      if (method === 'expectResultRegion') {
        return [
          'await productSearchPage.expectResultRegion();',
          `// Business assertion: ${action.expectation || 'product results region populated'}`,
        ];
      }
      if (method === 'openItemSearch') {
        return ['await authenticatedPage.openItemSearch();'];
      }
      if (method === 'expectLoaded') {
        return ['await productSearchPage.expectLoaded();'];
      }
      return [`// page_object ${action.page_object}.${method}()`];
    }
    case 'assert':
      if (action.page_object_method === 'expectResultRegion') {
        return [
          'await productSearchPage.expectResultRegion();',
          `// Business assertion: ${action.expectation || action.assertion_text || 'expected outcome'}`,
        ];
      }
      return [`// assert: ${action.expectation || action.assertion_text || 'business outcome'}`];
    case 'navigate':
      return ['// Navigate via existing fixtures/page objects during approved execution'];
    default:
      return [`// action ${action.type}`];
  }
}

function renderBody(actions) {
  const lines = [];
  for (const action of actions) {
    lines.push(...renderActionLine(action));
  }
  if (!lines.length) {
    lines.push('// No actions rendered');
  }
  lines.push("await recordStep('generated-draft-complete');");
  return lines;
}

function main() {
  const inputPath = process.argv[2];
  if (!inputPath) {
    console.log(JSON.stringify({ ok: false, error: 'usage: generate-spec-bridge.mjs <payload.json>' }));
    process.exit(1);
  }
  const payload = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
  const probe = probeRenderCode();
  const bodyLines = renderBody(payload.actions || []);

  console.log(
    JSON.stringify({
      ok: true,
      bridgeAvailable: probe.available,
      bridgeReason: probe.reason,
      playwrightVersion: playwrightVersion(),
      serializer: probe.available ? 'playwright-renderCode' : 'node-fallback-aligned',
      bodyLines,
    })
  );
}

main();
