import fs from 'fs';
import path from 'path';

export type LiveEventInput = {
  phase: string;
  action: string;
  target?: string;
  value_summary?: string;
  status?: string;
  duration_ms?: number;
  evidence_ref?: string;
  flow_id?: string;
  step_id?: string;
};

function eventsPath(): string | null {
  const configured = process.env.QA_LIVE_EVENTS_PATH;
  if (configured) return configured;
  const runId = process.env.QA_RUN_ID;
  if (!runId) return null;
  return path.resolve('reports/live-events', `${runId}.jsonl`);
}

export async function emitLiveEvent(input: LiveEventInput): Promise<void> {
  const file = eventsPath();
  if (!file) return;
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const payload = {
    run_id: process.env.QA_RUN_ID || '',
    timestamp: new Date().toISOString(),
    source: 'PLAYWRIGHT',
    flow_id: input.flow_id || process.env.QA_FLOW_ID || '',
    ...input,
  };
  fs.appendFileSync(file, `${JSON.stringify(payload)}\n`, 'utf8');
}

export function wrapPageLiveActions(page: import('@playwright/test').Page): void {
  const originalClick = page.click.bind(page);
  page.click = async (selector, options) => {
    await emitLiveEvent({ phase: 'ACTION', action: 'CLICK', target: String(selector) });
    const started = Date.now();
    try {
      await originalClick(selector, options);
      await emitLiveEvent({
        phase: 'ACTION',
        action: 'CLICK',
        target: String(selector),
        status: 'OK',
        duration_ms: Date.now() - started,
      });
    } catch (error) {
      await emitLiveEvent({
        phase: 'ACTION',
        action: 'CLICK',
        target: String(selector),
        status: 'FAIL',
        duration_ms: Date.now() - started,
        value_summary: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }
  };

  const originalFill = page.fill.bind(page);
  page.fill = async (selector, value, options) => {
    const sensitive = /password|pass/i.test(String(selector));
    await emitLiveEvent({
      phase: 'ACTION',
      action: 'FILL',
      target: String(selector),
      value_summary: sensitive ? '[redacted]' : String(value),
    });
    return originalFill(selector, value, options);
  };
}
