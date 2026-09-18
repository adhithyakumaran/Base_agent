import fs from 'fs';
import path from 'path';

export async function atomicWriteText(filePath: string, text: string): Promise<void> {
  await fs.promises.mkdir(path.dirname(filePath), { recursive: true });
  const tmp = `${filePath}.tmp.${process.pid}`;
  await fs.promises.writeFile(tmp, text, 'utf8');
  await fs.promises.rename(tmp, filePath);
}

export async function atomicWriteJson(filePath: string, payload: unknown): Promise<void> {
  await atomicWriteText(filePath, JSON.stringify(payload, null, 2));
}

function sleepMs(ms: number): void {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    /* spin */
  }
}

export async function withFileLock<T>(lockPath: string, fn: () => Promise<T>): Promise<T> {
  await fs.promises.mkdir(path.dirname(lockPath), { recursive: true });
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    try {
      await fs.promises.writeFile(lockPath, String(process.pid), { flag: 'wx' });
      break;
    } catch {
      sleepMs(20);
    }
  }
  try {
    return await fn();
  } finally {
    await fs.promises.unlink(lockPath).catch(() => undefined);
  }
}
