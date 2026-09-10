/**
 * Playwright/browser URL rules for APEX friendly URLs:
 *
 * 1. Paths starting with "/" resolve from domain root:
 *    base .../ea + "/login" → https://host/login (404)
 *
 * 2. Bare segments replace the last path segment (RFC 3986):
 *    base .../tjdcom/ea + "login" → .../tjdcom/login (drops "ea")
 *
 * Use "./login" to append, or resolveAppUrl() for an absolute URL.
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
  const stripped = raw.replace(/^\/+/, '');
  if (stripped.startsWith('./')) return stripped;
  return `./${stripped}`;
}

export function resolveAppUrl(
  baseURL: string,
  pathSegment: string | undefined,
  fallback: string
): string {
  const raw = (pathSegment ?? fallback).trim();
  if (/^https?:\/\//i.test(raw)) return raw;
  const segment = raw.replace(/^\/+/, '');
  return `${normalizeBaseUrl(baseURL)}/${segment}`;
}

export function loginRelativePath(): string {
  return toAppRelativePath(process.env.EA_LOGIN_URL, 'login');
}

export function homeRelativePath(): string {
  return toAppRelativePath(process.env.EA_HOME_URL, 'home');
}

export function loginUrl(): string {
  return resolveAppUrl(
    normalizeBaseUrl(process.env.EA_BASE_URL),
    process.env.EA_LOGIN_URL,
    'login'
  );
}

export function homeUrl(): string {
  return resolveAppUrl(
    normalizeBaseUrl(process.env.EA_BASE_URL),
    process.env.EA_HOME_URL,
    'home'
  );
}

/** @deprecated use loginRelativePath */
export function loginPath(): string {
  return loginRelativePath();
}

/** @deprecated use homeRelativePath */
export function homePath(): string {
  return homeRelativePath();
}

export function appPath(pathSegment: string): string {
  return toAppRelativePath(pathSegment, pathSegment);
}

export function appUrl(pathSegment: string): string {
  return resolveAppUrl(normalizeBaseUrl(process.env.EA_BASE_URL), pathSegment, pathSegment);
}
