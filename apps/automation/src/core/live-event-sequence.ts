import fs from 'fs';
import path from 'path';

function sleepMs(ms: number): void {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    /* spin */
  }
}

export function readMaxSequence(file: string): number {
  if (!fs.existsSync(file)) return 0;
  let max = 0;
  for (const line of fs.readFileSync(file, 'utf8').split('\n')) {
    if (!line.trim()) continue;
    try {
      const row = JSON.parse(line) as { sequence?: number };
      max = Math.max(max, Number(row.sequence || 0));
    } catch {
      /* skip malformed */
    }
  }
  return max;
}

export function withEventsFileLock<T>(file: string, fn: () => T): T {
  const lock = `${file}.lock`;
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    try {
      fs.writeFileSync(lock, `${process.pid}:${Date.now()}`, { flag: 'wx' });
      break;
    } catch {
      sleepMs(12);
    }
  }
  try {
    return fn();
  } finally {
    try {
      fs.unlinkSync(lock);
    } catch {
      /* ignore */
    }
  }
}

export function appendSequencedEvent(file: string, payload: Record<string, unknown>): number {
  return withEventsFileLock(file, () => {
    const sequence = readMaxSequence(file) + 1;
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.appendFileSync(file, `${JSON.stringify({ ...payload, sequence })}\n`, 'utf8');
    return sequence;
  });
}
