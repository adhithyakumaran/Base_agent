import fs from 'fs';
import path from 'path';
import type { BrowserContext } from '@playwright/test';
import { appendSequencedEvent } from './live-event-sequence';

let closed = false;

export function isLiveBrowserClosed(): boolean {
  return closed;
}

export function markLiveBrowserClosed(): void {
  closed = true;
}

export function resetLiveBrowserClosedForTests(): void {
  closed = false;
}

function profileDir(): string | null {
  return process.env.QA_LIVE_PROFILE_DIR || null;
}

function sessionMetaPath(dir: string): string {
  return path.join(dir, 'session.json');
}

function closeSignalPath(dir: string): string {
  return path.join(dir, 'close.signal');
}

function atomicWriteJson(filePath: string, payload: Record<string, unknown>): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const tmp = `${filePath}.tmp.${process.pid}`;
  fs.writeFileSync(tmp, JSON.stringify(payload, null, 2), 'utf8');
  fs.renameSync(tmp, filePath);
}

export function writeSessionMeta(partial: Record<string, unknown>): void {
  const dir = profileDir();
  if (!dir) return;
  const metaPath = sessionMetaPath(dir);
  let existing: Record<string, unknown> = {};
  if (fs.existsSync(metaPath)) {
    try {
      existing = JSON.parse(fs.readFileSync(metaPath, 'utf8')) as Record<string, unknown>;
    } catch {
      existing = {};
    }
  }
  atomicWriteJson(metaPath, { ...existing, ...partial });
}

function emitBrowserEvent(action: string, status: string, valueSummary = ''): void {
  const eventsFile = process.env.QA_LIVE_EVENTS_PATH;
  if (!eventsFile) return;
  appendSequencedEvent(eventsFile, {
    run_id: process.env.QA_RUN_ID || '',
    timestamp: new Date().toISOString(),
    source: 'PLAYWRIGHT',
    flow_id: process.env.QA_FLOW_ID || '',
    phase: 'BROWSER',
    action,
    target: '',
    value_summary: valueSummary,
    status,
    duration_ms: 0,
    evidence_ref: '',
    step_id: '',
  });
}

export async function gracefulCloseFromSignal(context: BrowserContext): Promise<boolean> {
  const dir = profileDir();
  if (!dir) return false;
  const signal = closeSignalPath(dir);
  if (!fs.existsSync(signal)) return false;

  const metaPath = sessionMetaPath(dir);
  let existing: Record<string, unknown> = {};
  if (fs.existsSync(metaPath)) {
    try {
      existing = JSON.parse(fs.readFileSync(metaPath, 'utf8')) as Record<string, unknown>;
    } catch {
      existing = {};
    }
  }
  if (existing.status === 'CLOSED') {
    try {
      fs.unlinkSync(signal);
    } catch {
      /* ignore */
    }
    markLiveBrowserClosed();
    return true;
  }

  markLiveBrowserClosed();
  emitBrowserEvent('CLOSE', 'OK');
  writeSessionMeta({
    status: 'CLOSED',
    closed_at: new Date().toISOString(),
  });
  try {
    await context.close();
  } catch {
    /* context may already be closing */
  }
  try {
    fs.unlinkSync(signal);
  } catch {
    /* ignore */
  }
  return true;
}

function markDisconnected(reason: string): void {
  if (isLiveBrowserClosed()) return;
  markLiveBrowserClosed();
  writeSessionMeta({
    status: 'BROWSER_DISCONNECTED',
    disconnected_at: new Date().toISOString(),
    disconnect_reason: reason,
  });
  emitBrowserEvent('DISCONNECT', 'OK', reason);
}

export async function watchCloseSignalWhileOpen(context: BrowserContext): Promise<void> {
  const dir = profileDir();
  if (!dir) return;
  const pollMs = Number(process.env.QA_LIVE_CLOSE_POLL_MS || 400);

  context.on('close', () => {
    markDisconnected('context_closed');
  });

  while (!isLiveBrowserClosed()) {
    const handled = await gracefulCloseFromSignal(context);
    if (handled) break;

    const browser = context.browser();
    if (!browser || !browser.isConnected() || context.pages().length === 0) {
      markDisconnected('browser_unavailable');
      try {
        await context.close();
      } catch {
        /* ignore */
      }
      break;
    }
    await new Promise((r) => setTimeout(r, pollMs));
  }
}
