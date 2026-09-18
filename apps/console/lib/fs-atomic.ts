import fs from "fs";
import path from "path";

const WIN32 = process.platform === "win32";

function sleepMs(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isTransientFsError(err: unknown): boolean {
  if (!err || typeof err !== "object") return false;
  const code = (err as NodeJS.ErrnoException).code;
  return code === "EPERM" || code === "EBUSY" || code === "EACCES" || code === "EXDEV";
}

async function replaceFileAtomic(targetPath: string, tmpPath: string): Promise<void> {
  const backoffMs = WIN32 ? [0, 25, 50, 100, 200, 400] : [0, 10, 25, 50, 100];
  let lastErr: unknown;

  for (const wait of backoffMs) {
    if (wait > 0) await sleepMs(wait);
    try {
      await fs.promises.rename(tmpPath, targetPath);
      return;
    } catch (err) {
      lastErr = err;
      if (!isTransientFsError(err)) break;
    }
  }

  if (WIN32 && isTransientFsError(lastErr)) {
    await fs.promises.copyFile(tmpPath, targetPath);
    await fs.promises.unlink(tmpPath).catch(() => undefined);
    return;
  }

  await fs.promises.unlink(tmpPath).catch(() => undefined);
  throw lastErr;
}

export async function atomicWriteText(filePath: string, text: string): Promise<void> {
  await fs.promises.mkdir(path.dirname(filePath), { recursive: true });
  const tmp = `${filePath}.tmp.${process.pid}.${Date.now()}`;
  await fs.promises.writeFile(tmp, text, "utf8");
  await replaceFileAtomic(filePath, tmp);
}

export async function atomicWriteJson(filePath: string, payload: unknown): Promise<void> {
  await atomicWriteText(filePath, JSON.stringify(payload, null, 2));
}

function sleepSyncMs(ms: number): void {
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
      await fs.promises.writeFile(lockPath, String(process.pid), { flag: "wx" });
      break;
    } catch {
      sleepSyncMs(20);
    }
  }
  try {
    return await fn();
  } finally {
    await fs.promises.unlink(lockPath).catch(() => undefined);
  }
}

/** Best-effort read while another writer may be replacing the file (Windows-safe). */
export async function readTextWithRetry(filePath: string, attempts = 8): Promise<string> {
  let lastErr: unknown;
  for (let i = 0; i < attempts; i += 1) {
    try {
      return await fs.promises.readFile(filePath, "utf8");
    } catch (err) {
      lastErr = err;
      if (isTransientFsError(err) || (err as NodeJS.ErrnoException).code === "ENOENT") {
        await sleepMs(15 * (i + 1));
        continue;
      }
      throw err;
    }
  }
  throw lastErr;
}
