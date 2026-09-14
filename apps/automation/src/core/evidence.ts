import type { Page, TestInfo } from '@playwright/test';
import fs from 'fs';
import path from 'path';

export type EvidenceCapture = {
  runId: string;
  testId: string;
  stepId: string;
  flowId?: string;
  label: string;
  screenshotPath: string;
  domPath: string;
  metaPath: string;
  url: string;
  capturedAt: string;
};

function sanitizeSegment(value: string, max = 96): string {
  return value.replace(/[^a-zA-Z0-9_-]+/g, '_').slice(0, max);
}

export function resolveRunId(testInfo: TestInfo): string {
  return (
    process.env.QA_RUN_ID?.trim() ||
    testInfo.project.metadata?.runId?.toString() ||
    `local-${testInfo.workerIndex}`
  );
}

export function resolveTestId(testInfo: TestInfo): string {
  const title = testInfo.title;
  const tcMatch = title.match(/TC-[A-Z0-9-]+/);
  if (tcMatch) return tcMatch[0];
  return sanitizeSegment(testInfo.titlePath.join('_'), 120);
}

export function resolveFlowId(): string | undefined {
  const raw = process.env.QA_FLOW_ID?.trim();
  if (raw) return raw.replace(/^@/, '');
  return undefined;
}

export function evidenceDir(testInfo: TestInfo, stepId: string): string {
  const runId = resolveRunId(testInfo);
  const testId = resolveTestId(testInfo);
  const dir = path.join('reports', 'evidence', runId, testId, sanitizeSegment(stepId, 72));
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

export async function captureStepEvidence(
  page: Page,
  testInfo: TestInfo,
  label: string
): Promise<EvidenceCapture> {
  const runId = resolveRunId(testInfo);
  const testId = resolveTestId(testInfo);
  const stepId = sanitizeSegment(label, 72);
  const dir = evidenceDir(testInfo, stepId);
  const base = path.join(dir, 'capture');
  const screenshotPath = `${base}.png`;
  const domPath = `${base}.html`;
  const metaPath = `${base}.json`;

  await page.screenshot({ path: screenshotPath, fullPage: true });
  const html = await page.content();
  fs.writeFileSync(domPath, html, 'utf8');

  const capture: EvidenceCapture = {
    runId,
    testId,
    stepId,
    flowId: resolveFlowId(),
    label,
    screenshotPath,
    domPath,
    metaPath,
    url: page.url(),
    capturedAt: new Date().toISOString(),
  };
  fs.writeFileSync(metaPath, JSON.stringify(capture, null, 2), 'utf8');

  await testInfo.attach(`${label}-screenshot`, { path: screenshotPath, contentType: 'image/png' });
  await testInfo.attach(`${label}-dom`, { path: domPath, contentType: 'text/html' });
  await testInfo.attach(`${label}-url`, { body: capture.url, contentType: 'text/plain' });

  return capture;
}

/** Attach screenshot + URL (legacy helper). */
export async function attachEvidence(page: Page, testInfo: TestInfo, label: string): Promise<void> {
  await captureStepEvidence(page, testInfo, label);
}

/** Wrap page to capture evidence before/after clicks and navigation. */
export function wrapPageWithEvidence(
  page: Page,
  testInfo: TestInfo,
  opts?: { liveEvents?: boolean }
): void {
  if (opts?.liveEvents) {
    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const { wrapPageLiveActions } = require('./live-events') as typeof import('./live-events');
      wrapPageLiveActions(page);
    } catch {
      /* optional */
    }
  }
  let busy = false;
  const snap = async (label: string) => {
    if (busy) return;
    busy = true;
    try {
      await captureStepEvidence(page, testInfo, label);
    } catch {
      /* non-fatal — evidence must not break tests */
    } finally {
      busy = false;
    }
  };

  page.on('framenavigated', () => {
    void snap('navigate');
  });

  const originalClick = page.click.bind(page);
  page.click = async (...args: Parameters<Page['click']>) => {
    await snap('pre-click');
    const result = await originalClick(...args);
    await page.waitForTimeout(250).catch(() => undefined);
    await snap('post-click');
    return result;
  };

  const originalFill = page.fill.bind(page);
  page.fill = async (...args: Parameters<Page['fill']>) => {
    await snap('pre-fill');
    const result = await originalFill(...args);
    await snap('post-fill');
    return result;
  };

  const originalGoto = page.goto.bind(page);
  page.goto = async (...args: Parameters<Page['goto']>) => {
    await snap('pre-goto');
    const result = await originalGoto(...args);
    await snap('post-goto');
    return result;
  };
}
