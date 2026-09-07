import { test, expect } from '@playwright/test';
import {
  appPath,
  appUrl,
  homeUrl,
  loginUrl,
  normalizeBaseUrl,
  resolveAppUrl,
  toAppRelativePath,
} from '../../src/core/app-url';

const BASE = 'https://dev-ea.titanrts.com/ords/r/tjdcom/ea';

test.describe('app-url helpers @unit', () => {
  test.beforeEach(() => {
    process.env.EA_BASE_URL = BASE;
    process.env.EA_LOGIN_URL = 'login';
    process.env.EA_HOME_URL = 'home';
  });

  test('normalizeBaseUrl strips trailing /login from base', () => {
    expect(normalizeBaseUrl(`${BASE}/login`)).toBe(BASE);
  });

  test('toAppRelativePath prefixes ./ so ea segment is kept', () => {
    expect(toAppRelativePath('/login', 'login')).toBe('./login');
    expect(toAppRelativePath('login', 'login')).toBe('./login');
  });

  test('resolveAppUrl builds full APEX login path', () => {
    expect(resolveAppUrl(BASE, 'login', 'login')).toBe(`${BASE}/login`);
    expect(resolveAppUrl(BASE, '/login', 'login')).toBe(`${BASE}/login`);
    expect(loginUrl()).toBe(`${BASE}/login`);
    expect(homeUrl()).toBe(`${BASE}/home`);
  });

  test('appPath and appUrl resolve in-app routes', () => {
    expect(appPath('rivaah')).toBe('./rivaah');
    expect(appUrl('administration')).toBe(`${BASE}/administration`);
  });
});
