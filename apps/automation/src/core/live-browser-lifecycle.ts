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

export function writeSessionMeta(partial: Record<string, unknown>): void {
  const dir = profileDir();
  if (!dir) return;
  fs.mkdirSync(dir, { recursive: true });
  const metaPath = sessionMetaPath(dir);
  let existing: Record<string, unknown> = {};
  if (fs.existsSync(metaPath)) {
    try {
      existing = JSON.parse(fs.readFileSync(metaPath, 'utf8')) as Record<string, unknown>;
    } catch {
      existing = {};
    }
  }
  fs.writeFileSync(metaPath, JSON.stringify({ ...existing, ...partial }, null, 2), 'utf8');
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
  const eventsFile = process.env.QA_LIVE_EVENTS_PATH;
  if (eventsFile) {
    appendSequencedEvent(eventsFile, {
      run_id: process.env.QA_RUN_ID || '',
      timestamp: new Date().toISOString(),
      source: 'PLAYWRIGHT',
      flow_id: process.env.QA_FLOW_ID || '',
      phase: 'BROWSER',
      action: 'CLOSE',
      target: '',
      value_summary: '',
      status: 'OK',
      duration_ms: 0,
      evidence_ref: '',
      step_id: '',
    });
  }
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

export async function watchCloseSignalWhileOpen(context: BrowserContext): Promise<void> {
  const dir = profileDir();
  if (!dir) return;
  const pollMs = Number(process.env.QA_LIVE_CLOSE_POLL_MS || 400);
  while (!isLiveBrowserClosed()) {
    const handled = await gracefulCloseFromSignal(context);
    if (handled) break;
    await new Promise((r) => setTimeout(r, pollMs));
  }
}
