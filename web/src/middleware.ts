// 1. The rules review page and its API exist only in local development.
// 2. Everything else (pages AND /data files) requires the shared password when SITE_PASSWORD is set.
//    In production the site fails closed: no SITE_PASSWORD → nothing is served.
import { NextResponse, type NextRequest } from "next/server";
import { AUTH_COOKIE, passwordToken } from "@/lib/auth";

const PUBLIC = ["/login", "/api/login", "/favicon.ico"];

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const prod = process.env.NODE_ENV === "production";

  if (prod && (pathname.startsWith("/rules") || pathname.startsWith("/api/rules"))) {
    return new NextResponse("Not found", { status: 404 });
  }
  if (PUBLIC.includes(pathname)) return NextResponse.next();

  const password = process.env.SITE_PASSWORD;
  if (!password) {
    return prod ? new NextResponse("Site password is not configured (set SITE_PASSWORD).", { status: 503 })
                : NextResponse.next();
  }
  if (req.cookies.get(AUTH_COOKIE)?.value === (await passwordToken(password))) return NextResponse.next();

  if (pathname.startsWith("/data/") || pathname.startsWith("/api/")) {
    return new NextResponse("Unauthorized", { status: 401 });
  }
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = `?next=${encodeURIComponent(pathname)}`;
  return NextResponse.redirect(url);
}

export const config = {
  // Skip Next.js build assets (JS/CSS chunks hold no data); everything else goes through the gate.
  matcher: ["/((?!_next/static|_next/image).*)"],
};
