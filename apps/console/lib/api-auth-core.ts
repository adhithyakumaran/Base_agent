const HEADER = "authorization";
const COOKIE_NAME = "scout_api";

function parseCookies(header: string | null): Record<string, string> {
  if (!header) return {};
  const out: Record<string, string> = {};
  for (const part of header.split(";")) {
    const [rawKey, ...rest] = part.split("=");
    const key = rawKey?.trim();
    if (!key) continue;
    out[key] = decodeURIComponent(rest.join("=").trim());
  }
  return out;
}

export function getScoutEnv(): "production" | "development" {
  const raw = (process.env.SCOUT_ENV || process.env.NODE_ENV || "development").toLowerCase();
  return raw === "production" ? "production" : "development";
}

export function allowInsecureLocal(): boolean {
  if (getScoutEnv() === "production") return false;
  const flag = (process.env.SCOUT_ALLOW_INSECURE_LOCAL ?? "true").trim().toLowerCase();
  return flag !== "false" && flag !== "0" && flag !== "off";
}

export function getConfiguredApiToken(): string | undefined {
  const token = process.env.SCOUT_API_TOKEN?.trim();
  return token || undefined;
}

export function getInternalServiceToken(): string | undefined {
  const internal = process.env.SCOUT_INTERNAL_API_TOKEN?.trim();
  if (internal) return internal;
  return getConfiguredApiToken();
}

export function authConfigurationError(): string | null {
  if (getScoutEnv() === "production" && !getConfiguredApiToken()) {
    return "SCOUT_API_TOKEN required in production";
  }
  return null;
}

export function extractBearerToken(req: Request): string | null {
  const header = req.headers.get(HEADER) || req.headers.get("x-scout-api-token") || "";
  if (!header) return null;
  if (header.toLowerCase().startsWith("bearer ")) {
    return header.slice(7).trim();
  }
  return header.trim();
}

export function extractAuthenticatedActor(req: Request): string {
  const actor = req.headers.get("x-scout-actor")?.trim();
  if (actor) return actor.slice(0, 120);
  const token = extractBearerToken(req);
  if (token) return `api-token:${token.slice(0, 8)}`;
  return "authenticated-client";
}

export function isAuthorizedRequest(req: Request): boolean {
  const misconfigured = authConfigurationError();
  if (misconfigured) return false;

  const configured = getConfiguredApiToken();
  if (!configured) {
    return allowInsecureLocal();
  }

  const provided = extractBearerToken(req);
  if (provided === configured) return true;

  const cookies = parseCookies(req.headers.get("cookie"));
  if (cookies[COOKIE_NAME] === configured) return true;

  return false;
}

export function shouldSetBrowserSessionCookie(): boolean {
  return (process.env.SCOUT_AUTO_BROWSER_SESSION ?? "true").trim().toLowerCase() !== "false";
}

export { COOKIE_NAME };
