const HEADER = "authorization";

export function getConfiguredApiToken(): string | undefined {
  const token = process.env.SCOUT_API_TOKEN?.trim();
  return token || undefined;
}

export function extractBearerToken(req: Request): string | null {
  const header = req.headers.get(HEADER) || req.headers.get("x-scout-api-token") || "";
  if (!header) return null;
  if (header.toLowerCase().startsWith("bearer ")) {
    return header.slice(7).trim();
  }
  return header.trim();
}

export function isAuthorizedRequest(req: Request): boolean {
  const configured = getConfiguredApiToken();
  if (!configured) return true;
  const provided = extractBearerToken(req);
  return provided === configured;
}
