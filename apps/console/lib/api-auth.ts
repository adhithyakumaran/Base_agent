import { NextResponse } from "next/server";
import {
  authConfigurationError,
  extractAuthenticatedActor,
  extractBearerToken,
  getConfiguredApiToken,
  isAuthorizedRequest,
} from "@/lib/api-auth-core";
export {
  authConfigurationError,
  extractAuthenticatedActor,
  extractBearerToken,
  getConfiguredApiToken,
  isAuthorizedRequest,
};
export { getInternalServiceToken, internalAgentHeaders, fetchInternalAgent } from "@/lib/internal-agent";

/**
 * Canonical BFF authentication boundary (P10.1).
 */
export function misconfiguredResponse(): NextResponse {
  return NextResponse.json(
    {
      error: "Service misconfigured",
      detail: authConfigurationError() || "Authentication not configured",
      security_boundary: "scout_api_token_v1",
    },
    { status: 503 }
  );
}

export function unauthorizedResponse(): NextResponse {
  return NextResponse.json(
    {
      error: "Unauthorized",
      detail: "Valid SCOUT_API_TOKEN required (Authorization: Bearer <token> or scout_api cookie)",
      security_boundary: "scout_api_token_v1",
    },
    { status: 401 }
  );
}

export function requireApiAuth(req: Request): NextResponse | null {
  if (authConfigurationError()) return misconfiguredResponse();
  if (isAuthorizedRequest(req)) return null;
  return unauthorizedResponse();
}

export function requireMutationAuth(req: Request): NextResponse | null {
  return requireApiAuth(req);
}

export async function requireRunAccess(req: Request, runId: string): Promise<NextResponse | null> {
  const denied = requireApiAuth(req);
  if (denied) return denied;
  const { assertRunAccessible } = await import("@/lib/run-access");
  const ok = await assertRunAccessible(runId);
  if (!ok) {
    return NextResponse.json(
      { error: "Forbidden", detail: "Run not accessible", run_id: runId },
      { status: 403 }
    );
  }
  return null;
}
