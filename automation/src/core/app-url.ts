/**
 * Playwright resolves paths starting with "/" from the domain root, not baseURL.
 * With EA_BASE_URL=https://host/ords/r/tjdcom/ea, goto("/login") becomes
 * https://host/login (404) instead of https://host/ords/r/tjdcom/ea/login.
 */

export function normalizeBaseUrl(raw: string | undefined): string {
  const fallback = 'https://uat.example.com/ords/r/tjdcom/ea';
  if (!raw) return fallback;
  let url = raw.trim().replace(/\/+$/, '');
  url = url.replace(/\/login\/?$/i, '');
  return url;
}

export function toAppRelativePath(pathSegment: string | undefined, fallback: string): string {
  const raw = (pathSegment ?? fallback).trim();
  if (/^https?:\/\//i.test(raw)) return raw;
  return raw.replace(/^\/+/, '');
}

export function resolveAppUrl(
  baseURL: string,
  pathSegment: string | undefined,
  fallback: string
): string {
  const segment = toAppRelativePath(pathSegment, fallback);
  if (/^https?:\/\//i.test(segment)) return segment;
  return `${normalizeBaseUrl(baseURL)}/${segment}`;
}

export function loginPath(): string {
  return toAppRelativePath(process.env.EA_LOGIN_URL, 'login');
}

export function homePath(): string {
  return toAppRelativePath(process.env.EA_HOME_URL, 'home');
}

export function appPath(pathSegment: string): string {
  return toAppRelativePath(pathSegment, pathSegment);
}
