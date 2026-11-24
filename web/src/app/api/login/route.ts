import { NextResponse } from "next/server";
import { AUTH_COOKIE, AUTH_MAX_AGE, passwordToken } from "@/lib/auth";

// Form POST from /login. Sets the auth cookie and returns to the page the visitor wanted.
export async function POST(req: Request) {
  const form = await req.formData();
  const given = String(form.get("password") ?? "");
  const rawNext = String(form.get("next") ?? "/");
  const next = rawNext.startsWith("/") && !rawNext.startsWith("//") ? rawNext : "/"; // no open redirects
  const expected = process.env.SITE_PASSWORD;

  if (!expected || given !== expected) {
    await new Promise((r) => setTimeout(r, 600)); // slow down guessing
    return NextResponse.redirect(new URL(`/login?error=1&next=${encodeURIComponent(next)}`, req.url), 303);
  }
  const res = NextResponse.redirect(new URL(next, req.url), 303);
  res.cookies.set(AUTH_COOKIE, await passwordToken(expected), {
    httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: AUTH_MAX_AGE,
  });
  return res;
}
