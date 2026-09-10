#!/usr/bin/env node
/** Validate automation/config/.env before Playwright runs */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ENV_FILE = path.join(ROOT, 'config', '.env');

function fail(message) {
  console.error(`[env-check] FAIL: ${message}`);
  process.exitCode = 1;
}

function ok(message) {
  console.log(`[env-check] OK: ${message}`);
}

if (!fs.existsSync(ENV_FILE)) {
  fail(`Missing ${ENV_FILE} — copy config/environments.example.env to config/.env`);
  process.exit(process.exitCode ?? 1);
}

const envText = fs.readFileSync(ENV_FILE, 'utf8');
const env = Object.fromEntries(
  envText
    .split('\n')
    .filter((line) => line.trim() && !line.trim().startsWith('#'))
    .map((line) => {
      const idx = line.indexOf('=');
      return [line.slice(0, idx).trim(), line.slice(idx + 1).trim()];
    })
);

const base = env.EA_BASE_URL ?? '';
const login = env.EA_LOGIN_URL ?? '';
const home = env.EA_HOME_URL ?? '';

if (!base.includes('/ords/r/tjdcom/ea')) {
  fail(`EA_BASE_URL should end with /ords/r/tjdcom/ea (got: ${base || '[empty]'})`);
} else {
  ok(`EA_BASE_URL=${base}`);
}

if (/\/login\/?$/i.test(base)) {
  fail('EA_BASE_URL must not include /login — use EA_LOGIN_URL instead');
}

if (login.startsWith('/') && !login.startsWith('./')) {
  fail(
    `EA_LOGIN_URL=${login} resolves to domain root (/login → host/login). Use "login" or "./login" instead.`
  );
} else {
  ok(`EA_LOGIN_URL=${login || 'login (default)'}`);
}

if (home.startsWith('/') && !home.startsWith('./')) {
  fail(`EA_HOME_URL=${home} must not start with "/" unless it is "./home"`);
} else {
  ok(`EA_HOME_URL=${home || 'home (default)'}`);
}

if (!env.EA_USER_USERNAME || !env.EA_USER_PASSWORD) {
  fail('EA_USER_USERNAME and EA_USER_PASSWORD must be set for authenticated flows');
} else {
  ok('UAT credentials configured');
}

if (process.exitCode) {
  console.error('\nFix automation/config/.env then rerun tests.');
  process.exit(1);
}

console.log('[env-check] Environment ready for Playwright.');
