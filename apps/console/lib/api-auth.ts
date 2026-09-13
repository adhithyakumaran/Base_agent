import { NextResponse } from "next/server";
import {
  extractBearerToken,
  getConfiguredApiToken,
  isAuthorizedRequest,
} from "@/lib/api-auth-core";

export { extractBearerToken, getConfiguredApiToken, isAuthorizedRequest };

/**
 * Minimum viable API boundary — not full enterprise RBAC.
 * Set SCOUT_API_TOKEN in the console environment to enable auth checks.
 */
export function unauthorizedResponse(): NextResponse {
  return NextResponse.json(
    {
      error: "Unauthorized",
      detail: "Valid SCOUT_API_TOKEN required (Authorization: Bearer <token>)",
      security_boundary: "scout_api_token_v1",
    },
    { status: 401 }
  );
}

export function requireApiAuth(req: Request): NextResponse | null {
  if (isAuthorizedRequest(req)) return null;
  return unauthorizedResponse();
}

export function requireMutationAuth(req: Request): NextResponse | null {
  return requireApiAuth(req);
}
