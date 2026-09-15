import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import {
  authConfigurationError,
  COOKIE_NAME,
  getConfiguredApiToken,
  isAuthorizedRequest,
  shouldSetBrowserSessionCookie,
} from "@/lib/api-auth-core";

export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  if (pathname.startsWith("/api/")) {
    const misconfigured = authConfigurationError();
    if (misconfigured) {
      return NextResponse.json(
        { error: "Service misconfigured", detail: misconfigured },
        { status: 503 }
      );
    }
    if (!isAuthorizedRequest(request)) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    return NextResponse.next();
  }

  const token = getConfiguredApiToken();
  if (token && shouldSetBrowserSessionCookie() && !request.cookies.get(COOKIE_NAME)) {
    const response = NextResponse.next();
    response.cookies.set(COOKIE_NAME, token, {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      secure: process.env.SCOUT_ENV === "production",
    });
    return response;
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
