// Shared-password gate. The cookie holds a SHA-256 of the password (never the password itself),
// so changing SITE_PASSWORD on Vercel logs everyone out.
export const AUTH_COOKIE = "zu_auth";
export const AUTH_MAX_AGE = 60 * 60 * 24 * 30; // 30 days

export async function passwordToken(password: string): Promise<string> {
  const data = new TextEncoder().encode(`zoning-upside:${password}`);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
