#!/usr/bin/env node
/** Resolve locator chain with approved healing overlays — used by tests and diagnostics. */
import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { fileURLToPath } from 'url';

const automationDir = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const SCHEMA = 'healing_locator_overlay_v1';

function parseArgs(argv) {
  const out = { overlayPath: '', label: '', flowId: '', testId: '', stepId: '', chain: '[]', enabled: 'true' };
  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--overlay') out.overlayPath = argv[++i];
    else if (arg === '--label') out.label = argv[++i];
    else if (arg === '--flow') out.flowId = argv[++i];
    else if (arg === '--test') out.testId = argv[++i];
    else if (arg === '--step') out.stepId = argv[++i];
    else if (arg === '--chain') out.chain = argv[++i];
    else if (arg === '--enabled') out.enabled = argv[++i];
  }
  return out;
}

function validateEntry(entry) {
  if (!entry || typeof entry !== 'object') return null;
  if (entry.status !== 'APPROVED' || entry.revoked) return null;
  if (!Array.isArray(entry.selectors) || !entry.selectors.length) return null;
  if (!entry.healing_id || !entry.flow_id || !entry.locator_label) return null;
  return entry;
}

function loadStore(overlayPath) {
  if (!fs.existsSync(overlayPath)) return null;
  try {
    const raw = JSON.parse(fs.readFileSync(overlayPath, 'utf8'));
    if (raw.schema === SCHEMA && Array.isArray(raw.entries)) {
      return {
        overlay_version: raw.overlay_version || '',
        overlay_hash: raw.overlay_hash || '',
        entries: raw.entries.map(validateEntry).filter(Boolean),
      };
    }
    return null;
  } catch {
    return null;
  }
}

function resolve(args) {
  if (['0', 'false', 'no'].includes(String(args.enabled).toLowerCase())) {
    const base = JSON.parse(args.chain);
    return { ok: true, chain: base, meta: { locator_source: 'KB_CHAIN', selectors_applied: base } };
  }
  const store = loadStore(args.overlayPath);
  const base = JSON.parse(args.chain);
  if (!store) {
    return { ok: true, chain: base, meta: { locator_source: 'KB_CHAIN', selectors_applied: base } };
  }
  const matches = store.entries.filter((entry) => {
    if (entry.flow_id !== args.flowId) return false;
    if (entry.locator_label !== args.label) return false;
    if (entry.test_id && args.testId && entry.test_id !== args.testId) return false;
    if (entry.step_id && args.stepId && entry.step_id !== args.stepId) return false;
    return true;
  });
  if (!matches.length) {
    return { ok: true, chain: base, meta: { locator_source: 'KB_CHAIN', selectors_applied: base } };
  }
  matches.sort((a, b) => String(b.approved_at || '').localeCompare(String(a.approved_at || '')));
  const best = matches[0];
  const chain = [...best.selectors, ...base];
  return {
    ok: true,
    chain,
    meta: {
      locator_source: 'HEALING_OVERLAY',
      healing_id: best.healing_id,
      overlay_version: store.overlay_version,
      overlay_hash: store.overlay_hash,
      selectors_applied: best.selectors,
    },
  };
}

const args = parseArgs(process.argv);
const overlayPath = args.overlayPath || path.join(automationDir, 'healing', 'approved', 'locator-overlays.json');
const result = resolve({ ...args, overlayPath });
console.log(JSON.stringify(result));
