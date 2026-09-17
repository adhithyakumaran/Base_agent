import fs from 'fs';
import path from 'path';
import crypto from 'crypto';

export type LocatorChain = string[];

export type OverlayEntry = {
  healing_id: string;
  flow_id: string;
  test_id?: string;
  step_id?: string;
  locator_label: string;
  status: string;
  revoked?: boolean;
  selectors: string[];
  old_locator?: string;
  new_locator?: string;
  approved_at?: string;
  entry_version?: number;
};

export type OverlayStore = {
  schema: string;
  overlay_version: string;
  overlay_hash: string;
  entries: OverlayEntry[];
};

export type OverlayUsageMeta = {
  locator_source: 'HEALING_OVERLAY' | 'HEALING_OVERRIDE' | 'KB_CHAIN';
  healing_id?: string;
  overlay_version?: string;
  overlay_hash?: string;
  locator_label: string;
  flow_id?: string;
  selectors_applied: string[];
};

const SCHEMA = 'healing_locator_overlay_v1';
let cachedStore: OverlayStore | null | undefined;
let loadErrors: string[] = [];

export function overlaysEnabled(): boolean {
  const raw = process.env.QA_HEALING_OVERLAYS_ENABLED;
  if (raw === undefined) return true;
  return !['0', 'false', 'no'].includes(raw.toLowerCase());
}

export function getOverlayLoadErrors(): string[] {
  return [...loadErrors];
}

function overlaysFilePath(): string {
  return path.join(process.cwd(), 'healing', 'approved', 'locator-overlays.json');
}

function usageLogPath(): string {
  const runId = process.env.QA_RUN_ID?.trim() || 'local';
  const dir = path.join(process.cwd(), 'reports', 'healing');
  fs.mkdirSync(dir, { recursive: true });
  return path.join(dir, `overlay-usage-${runId}.jsonl`);
}

function computeHash(entries: OverlayEntry[]): string {
  return crypto.createHash('sha256').update(JSON.stringify({ schema: SCHEMA, entries }), 'utf8').digest('hex');
}

function validateEntry(raw: unknown): OverlayEntry | null {
  if (!raw || typeof raw !== 'object') return null;
  const entry = raw as OverlayEntry;
  if (!entry.healing_id || !entry.flow_id || !entry.locator_label) return null;
  if (entry.status !== 'APPROVED') return null;
  if (entry.revoked) return null;
  if (!Array.isArray(entry.selectors) || entry.selectors.length === 0) return null;
  if (!entry.selectors.every((s) => typeof s === 'string' && s.trim())) return null;
  return entry;
}

function migrateLegacy(raw: Record<string, unknown>): OverlayStore {
  const entries: OverlayEntry[] = [];
  for (const [flowId, labels] of Object.entries(raw)) {
    if (flowId === 'schema' || flowId === 'overlay_version' || flowId === 'overlay_hash' || flowId === 'entries') {
      continue;
    }
    if (!labels || typeof labels !== 'object' || Array.isArray(labels)) continue;
    for (const [locatorLabel, selectors] of Object.entries(labels as Record<string, string[]>)) {
      if (!Array.isArray(selectors)) continue;
      entries.push({
        healing_id: `legacy-${flowId}-${locatorLabel}`,
        flow_id: flowId,
        locator_label: locatorLabel,
        status: 'APPROVED',
        revoked: false,
        selectors,
        entry_version: 1,
      });
    }
  }
  return {
    schema: SCHEMA,
    overlay_version: new Date().toISOString().replace(/[-:]/g, '').slice(0, 15),
    overlay_hash: computeHash(entries),
    entries,
  };
}

export function loadOverlayStore(forceReload = false): OverlayStore | null {
  if (!overlaysEnabled()) {
    cachedStore = null;
    return null;
  }
  if (!forceReload && cachedStore !== undefined) {
    return cachedStore;
  }
  loadErrors = [];
  const filePath = overlaysFilePath();
  if (!fs.existsSync(filePath)) {
    cachedStore = null;
    return null;
  }
  try {
    const raw = JSON.parse(fs.readFileSync(filePath, 'utf8')) as Record<string, unknown>;
    if (raw.schema === SCHEMA && Array.isArray(raw.entries)) {
      const entries = raw.entries.map(validateEntry).filter((e): e is OverlayEntry => e !== null);
      cachedStore = {
        schema: SCHEMA,
        overlay_version: String(raw.overlay_version || ''),
        overlay_hash: String(raw.overlay_hash || computeHash(entries)),
        entries,
      };
      if (entries.length !== raw.entries.length) {
        loadErrors.push('invalid overlay entries ignored during load');
      }
      return cachedStore;
    }
    cachedStore = migrateLegacy(raw);
    return cachedStore;
  } catch (err) {
    loadErrors.push(`corrupt overlay file ignored: ${(err as Error).message}`);
    cachedStore = null;
    return null;
  }
}

export function resetOverlayCache(): void {
  cachedStore = undefined;
  loadErrors = [];
}

function readTemporaryOverride(label: string): string[] | null {
  const raw = process.env.QA_HEALING_LOCATOR_OVERRIDE;
  if (!raw) return null;
  try {
    const map = JSON.parse(raw) as Record<string, string[]>;
    const extra = map[label];
    return extra?.length ? extra : null;
  } catch {
    loadErrors.push('invalid QA_HEALING_LOCATOR_OVERRIDE ignored');
    return null;
  }
}

function resolveFlowId(): string | undefined {
  const raw = process.env.QA_FLOW_ID?.trim();
  return raw ? raw.replace(/^@/, '') : undefined;
}

function resolveTestId(): string | undefined {
  return process.env.QA_TEST_ID?.trim() || undefined;
}

function resolveStepId(): string | undefined {
  return process.env.QA_STEP_ID?.trim() || undefined;
}

function findApprovedOverlay(label: string): OverlayUsageMeta | null {
  const store = loadOverlayStore();
  const flowId = resolveFlowId();
  if (!store || !flowId) return null;

  const testId = resolveTestId() || '';
  const stepId = resolveStepId() || '';
  const matches = store.entries.filter((entry) => {
    if (entry.flow_id !== flowId) return false;
    if (entry.locator_label !== label) return false;
    if (entry.test_id && testId && entry.test_id !== testId) return false;
    if (entry.step_id && stepId && entry.step_id !== stepId) return false;
    return true;
  });
  if (!matches.length) return null;
  matches.sort((a, b) => String(b.approved_at || '').localeCompare(String(a.approved_at || '')));
  const best = matches[0];
  return {
    locator_source: 'HEALING_OVERLAY',
    healing_id: best.healing_id,
    overlay_version: store.overlay_version,
    overlay_hash: store.overlay_hash,
    locator_label: label,
    flow_id: flowId,
    selectors_applied: [...best.selectors],
  };
}

export function recordOverlayUsage(meta: OverlayUsageMeta): void {
  if (meta.locator_source === 'KB_CHAIN') return;
  try {
    const line = JSON.stringify({ ...meta, recorded_at: new Date().toISOString() }) + '\n';
    fs.appendFileSync(usageLogPath(), line, 'utf8');
  } catch {
    /* non-fatal */
  }
}

export function resolveLocatorChain(
  chain: LocatorChain,
  label: string
): { chain: LocatorChain; meta: OverlayUsageMeta } {
  const override = readTemporaryOverride(label);
  if (override?.length) {
    const meta: OverlayUsageMeta = {
      locator_source: 'HEALING_OVERRIDE',
      locator_label: label,
      flow_id: resolveFlowId(),
      selectors_applied: override,
    };
    recordOverlayUsage(meta);
    return { chain: [...override, ...chain], meta };
  }

  const overlay = findApprovedOverlay(label);
  if (overlay?.selectors_applied.length) {
    recordOverlayUsage(overlay);
    return { chain: [...overlay.selectors_applied, ...chain], meta: overlay };
  }

  return {
    chain,
    meta: {
      locator_source: 'KB_CHAIN',
      locator_label: label,
      flow_id: resolveFlowId(),
      selectors_applied: [...chain],
    },
  };
}

export function getLastOverlayUsage(label: string): OverlayUsageMeta | undefined {
  const logPath = usageLogPath();
  if (!fs.existsSync(logPath)) return undefined;
  const lines = fs.readFileSync(logPath, 'utf8').trim().split('\n').filter(Boolean);
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    try {
      const parsed = JSON.parse(lines[i]) as OverlayUsageMeta;
      if (parsed.locator_label === label) return parsed;
    } catch {
      continue;
    }
  }
  return undefined;
}
