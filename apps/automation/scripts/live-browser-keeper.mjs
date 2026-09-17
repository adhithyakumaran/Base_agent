#!/usr/bin/env node
/**
 * Detached keeper for QA_KEEP_BROWSER_OPEN=true — polls close.signal and closes
 * the persistent Chrome session via CDP (DevToolsActivePort in profile dir).
 */
import fs from 'fs';
import path from 'path';
import { chromium } from 'playwright';

const profileDir = process.env.QA_LIVE_PROFILE_DIR;
if (!profileDir) {
  process.exit(0);
}

const pollMs = Number(process.env.QA_LIVE_CLOSE_POLL_MS || 400);
const signalPath = path.join(profileDir, 'close.signal');
const metaPath = path.join(profileDir, 'session.json');

function readMeta() {
  try {
    return JSON.parse(fs.readFileSync(metaPath, 'utf8'));
  } catch {
    return {};
  }
}

function writeMeta(partial) {
  const next = { ...readMeta(), ...partial };
  fs.mkdirSync(profileDir, { recursive: true });
  const tmp = `${metaPath}.tmp.${process.pid}`;
  fs.writeFileSync(tmp, JSON.stringify(next, null, 2), 'utf8');
  fs.renameSync(tmp, metaPath);
}

function devToolsPort() {
  const portFile = path.join(profileDir, 'DevToolsActivePort');
  if (!fs.existsSync(portFile)) return null;
  const line = fs.readFileSync(portFile, 'utf8').split('\n')[0]?.trim();
  return line || null;
}

async function closeBrowserViaCdp() {
  const port = devToolsPort();
  if (!port) return false;
  try {
    const browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
    await browser.close();
    return true;
  } catch {
    return false;
  }
}

async function handleCloseSignal() {
  const meta = readMeta();
  if (meta.status === 'CLOSED') {
    try {
      fs.unlinkSync(signalPath);
    } catch {
      /* ignore */
    }
    return true;
  }
  await closeBrowserViaCdp();
  writeMeta({
    status: 'CLOSED',
    closed_at: new Date().toISOString(),
    closed_by: 'live-browser-keeper',
  });
  try {
    fs.unlinkSync(signalPath);
  } catch {
    /* ignore */
  }
  return true;
}

async function main() {
  writeMeta({ keeper_pid: process.pid, keeper_started_at: new Date().toISOString() });
  while (true) {
    if (fs.existsSync(signalPath)) {
      await handleCloseSignal();
      break;
    }
    const meta = readMeta();
    if (meta.status === 'BROWSER_DISCONNECTED' || meta.status === 'CLOSED') {
      break;
    }
    await new Promise((r) => setTimeout(r, pollMs));
  }
}

main().catch(() => process.exit(1));
