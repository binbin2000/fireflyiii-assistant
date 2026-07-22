import { NextResponse } from "next/server";
import type { NextFetchEvent } from "next/server";
import { auth } from "@/auth";
import type { NextAuthRequest } from "next-auth";
import { isOidcConfigured, isOidcPartiallyConfigured } from "@/lib/auth-status";

const PUBLIC_PATHS = ["/login", "/api/auth"];

function isPublicPath(pathname: string) {
  return PUBLIC_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`));
}

// The second param's explicit NextFetchEvent type steers NextAuth's overloaded
// `auth()` toward the middleware signature instead of the route-handler one.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export default auth((request: NextAuthRequest, event: NextFetchEvent) => {
  const { pathname } = request.nextUrl;

  if (isOidcPartiallyConfigured()) {
    if (isPublicPath(pathname)) {
      return NextResponse.next();
    }

    if (pathname.startsWith("/api/")) {
      return NextResponse.json(
        { error: "Authentication is not correctly configured" },
        { status: 503 },
      );
    }

    return NextResponse.redirect(new URL("/login", request.nextUrl.origin));
  }

  if (!isOidcConfigured()) {
    return NextResponse.next();
  }

  if (isPublicPath(pathname) || request.auth) {
    return NextResponse.next();
  }

  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const loginUrl = new URL("/login", request.nextUrl.origin);
  loginUrl.searchParams.set("callbackUrl", pathname);
  return NextResponse.redirect(loginUrl);
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
