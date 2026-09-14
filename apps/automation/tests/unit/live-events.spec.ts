import fs from 'fs';
import os from 'os';
import path from 'path';
import { test, expect } from '@playwright/test';
import { appendSequencedEvent, readMaxSequence } from '../../src/core/live-event-sequence';
import {
  emitLiveEvent,
  instrumentLocator,
  readLiveEventsFromFile,
  summarizeFillValue,
} from '../../src/core/live-events';
import { resetLiveBrowserClosedForTests } from '../../src/core/live-browser-lifecycle';

test.describe('live events', () => {
  test('sequenced append starts at 1 and increments', async () => {
    const file = path.join(os.tmpdir(), `live-events-${Date.now()}.jsonl`);
    const seq1 = appendSequencedEvent(file, { phase: 'BROWSER', action: 'LAUNCH', status: 'OK' });
    const seq2 = appendSequencedEvent(file, { phase: 'ACTION', action: 'CLICK', status: 'STARTED' });
    const seq3 = appendSequencedEvent(file, { phase: 'ACTION', action: 'CLICK', status: 'OK' });
    expect(seq1).toBe(1);
    expect(seq2).toBe(2);
    expect(seq3).toBe(3);
    expect(readMaxSequence(file)).toBe(3);
    fs.unlinkSync(file);
  });

  test('emitLiveEvent assigns monotonic sequence across types', async () => {
    const file = path.join(os.tmpdir(), `live-events-${Date.now()}-b.jsonl`);
    process.env.QA_LIVE_EVENTS_PATH = file;
    process.env.QA_RUN_ID = 'run-seq';
    resetLiveBrowserClosedForTests();
    await emitLiveEvent({ phase: 'PLAN', action: 'SELECT', status: 'OK' });
    await emitLiveEvent({ phase: 'NAVIGATE', action: 'OPEN', target: '/home' });
    await emitLiveEvent({ phase: 'ACTION', action: 'FILL', target: '#sku', value_summary: 'ABC123', status: 'STARTED' });
    const rows = readLiveEventsFromFile(file);
    expect(rows.map((r) => r.sequence)).toEqual([1, 2, 3]);
    fs.unlinkSync(file);
    delete process.env.QA_LIVE_EVENTS_PATH;
    delete process.env.QA_RUN_ID;
  });

  test('locator click emits STARTED then OK', async () => {
    const file = path.join(os.tmpdir(), `live-events-${Date.now()}-c.jsonl`);
    process.env.QA_LIVE_EVENTS_PATH = file;
    process.env.QA_RUN_ID = 'run-click';
    resetLiveBrowserClosedForTests();

    const clicks: string[] = [];
    const fake = {
      click: async () => {
        clicks.push('clicked');
      },
    };
    const wrapped = instrumentLocator(fake as unknown as import('@playwright/test').Locator, 'button.search');
    await wrapped.click();
    expect(clicks).toEqual(['clicked']);
    const rows = readLiveEventsFromFile(file);
    expect(rows).toHaveLength(2);
    expect(rows[0].action).toBe('CLICK');
    expect(rows[0].status).toBe('STARTED');
    expect(rows[1].status).toBe('OK');
    fs.unlinkSync(file);
    delete process.env.QA_LIVE_EVENTS_PATH;
    delete process.env.QA_RUN_ID;
  });

  test('locator fill redaction', async () => {
    expect(summarizeFillValue('#P9999_USERNAME', 'demo_user')).toBe('demo_user');
    expect(summarizeFillValue('input[name=password]', 'secret123')).toBe('[redacted]');
    expect(summarizeFillValue('#P2_ITEM_CODE', 'ABC123')).toBe('ABC123');
    expect(summarizeFillValue('input[name=api_token]', 'tok')).toBe('[redacted]');
  });
});
