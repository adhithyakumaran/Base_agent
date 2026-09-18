import fs from 'fs';
import path from 'path';
import type { Locator, Page } from '@playwright/test';
import { appendSequencedEvent } from './live-event-sequence';
import { isSensitiveTarget, summarizeFillValue } from './live-redaction';
import { isLiveBrowserClosed, markLiveBrowserClosed } from './live-browser-lifecycle';

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

function basePayload(input: LiveEventInput): Record<string, unknown> {
  return {
    run_id: process.env.QA_RUN_ID || '',
    timestamp: new Date().toISOString(),
    source: 'PLAYWRIGHT',
    flow_id: input.flow_id || process.env.QA_FLOW_ID || '',
    phase: input.phase,
    action: input.action,
    target: input.target || '',
    value_summary: input.value_summary || '',
    status: input.status || 'OK',
    duration_ms: input.duration_ms || 0,
    evidence_ref: input.evidence_ref || '',
    step_id: input.step_id || '',
  };
}

export async function emitLiveEvent(input: LiveEventInput): Promise<void> {
  const file = eventsPath();
  if (!file) return;
  if (isLiveBrowserClosed() && input.phase === 'ACTION') {
    throw new Error('LIVE_BROWSER_CLOSED: action blocked after browser close');
  }
  appendSequencedEvent(file, basePayload(input));
}

function assertActionAllowed(): void {
  if (isLiveBrowserClosed()) {
    throw new Error('LIVE_BROWSER_CLOSED: action blocked after browser close');
  }
}

async function instrumentAction(
  action: 'CLICK' | 'CHECK',
  targetLabel: string,
  fn: () => Promise<void>
): Promise<void> {
  assertActionAllowed();
  await emitLiveEvent({ phase: 'ACTION', action, target: targetLabel, status: 'STARTED' });
  const started = Date.now();
  try {
    await fn();
    await emitLiveEvent({
      phase: 'ACTION',
      action,
      target: targetLabel,
      status: 'OK',
      duration_ms: Date.now() - started,
    });
  } catch (error) {
    await emitLiveEvent({
      phase: 'ACTION',
      action,
      target: targetLabel,
      status: 'FAIL',
      duration_ms: Date.now() - started,
      value_summary: error instanceof Error ? error.message : String(error),
    });
    throw error;
  }
}

async function instrumentFill(
  targetLabel: string,
  value: unknown,
  fn: () => Promise<void>
): Promise<void> {
  assertActionAllowed();
  const summary = summarizeFillValue(targetLabel, value);
  await emitLiveEvent({
    phase: 'ACTION',
    action: 'FILL',
    target: targetLabel,
    value_summary: summary,
    status: 'STARTED',
  });
  const started = Date.now();
  try {
    await fn();
    await emitLiveEvent({
      phase: 'ACTION',
      action: 'FILL',
      target: targetLabel,
      value_summary: summary,
      status: 'OK',
      duration_ms: Date.now() - started,
    });
  } catch (error) {
    await emitLiveEvent({
      phase: 'ACTION',
      action: 'FILL',
      target: targetLabel,
      value_summary: error instanceof Error ? error.message : String(error),
      status: 'FAIL',
      duration_ms: Date.now() - started,
    });
    throw error;
  }
}

async function instrumentSelectOption(
  targetLabel: string,
  values: unknown,
  fn: () => Promise<void>
): Promise<void> {
  assertActionAllowed();
  const summary = Array.isArray(values) ? values.join(',') : String(values ?? '');
  await emitLiveEvent({
    phase: 'ACTION',
    action: 'SELECT',
    target: targetLabel,
    value_summary: summary,
    status: 'STARTED',
  });
  const started = Date.now();
  try {
    await fn();
    await emitLiveEvent({
      phase: 'ACTION',
      action: 'SELECT',
      target: targetLabel,
      value_summary: summary,
      status: 'OK',
      duration_ms: Date.now() - started,
    });
  } catch (error) {
    await emitLiveEvent({
      phase: 'ACTION',
      action: 'SELECT',
      target: targetLabel,
      status: 'FAIL',
      duration_ms: Date.now() - started,
      value_summary: error instanceof Error ? error.message : String(error),
    });
    throw error;
  }
}

const CHAIN_METHODS = new Set([
  'first',
  'last',
  'nth',
  'filter',
  'locator',
  'getByRole',
  'getByText',
  'getByLabel',
  'getByPlaceholder',
  'getByTestId',
]);

export function instrumentLocator(loc: Locator, targetLabel: string): Locator {
  return new Proxy(loc, {
    get(target, prop, receiver) {
      const value = Reflect.get(target, prop, receiver);
      if (typeof value !== 'function') return value;
      const name = String(prop);
      if (name === 'click') {
        return (options?: Parameters<Locator['click']>[0]) =>
          instrumentAction('CLICK', targetLabel, () => target.click(options));
      }
      if (name === 'check') {
        return (options?: Parameters<Locator['check']>[0]) =>
          instrumentAction('CHECK', targetLabel, () => target.check(options));
      }
      if (name === 'fill') {
        return (fillValue: string, options?: Parameters<Locator['fill']>[1]) =>
          instrumentFill(targetLabel, fillValue, () => target.fill(fillValue, options));
      }
      if (name === 'selectOption') {
        return (...args: Parameters<Locator['selectOption']>) =>
          instrumentSelectOption(targetLabel, args[0], () => target.selectOption(...args));
      }
      if (CHAIN_METHODS.has(name)) {
        return (...args: unknown[]) => {
          const next = (value as (...a: unknown[]) => Locator).apply(target, args);
          const suffix =
            name === 'nth' ? `.nth(${String(args[0])})` : name === 'filter' ? `.filter(...)` : `.${name}()`;
          return instrumentLocator(next, `${targetLabel}${suffix}`);
        };
      }
      return value.bind(target);
    },
  });
}

function describeSelector(selector: string | Parameters<Page['locator']>[0]): string {
  return typeof selector === 'string' ? selector : String(selector);
}

export function wrapPageLiveActions(page: Page): void {
  const originalLocator = page.locator.bind(page);
  page.locator = (selector, options) => {
    const label = describeSelector(selector);
    return instrumentLocator(originalLocator(selector, options), label);
  };

  const originalClick = page.click.bind(page);
  page.click = async (selector, options) => {
    const target = String(selector);
    return instrumentAction('CLICK', target, () => originalClick(selector, options));
  };

  const originalFill = page.fill.bind(page);
  page.fill = async (selector, value, options) => {
    const target = String(selector);
    return instrumentFill(target, value, () => originalFill(selector, value, options));
  };
}

export function readLiveEventsFromFile(file: string): Array<Record<string, unknown>> {
  if (!fs.existsSync(file)) return [];
  const rows: Array<Record<string, unknown>> = [];
  for (const line of fs.readFileSync(file, 'utf8').split('\n')) {
    if (!line.trim()) continue;
    try {
      rows.push(JSON.parse(line) as Record<string, unknown>);
    } catch {
      /* skip */
    }
  }
  return rows;
}

/** @internal test helper */
export { isSensitiveTarget, summarizeFillValue };
