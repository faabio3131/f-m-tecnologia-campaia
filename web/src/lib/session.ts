import { cookies } from "next/headers";
import type { Me } from "@/contracts/types";

/**
 * WP-02: server-only session read. Runs on the Next.js server (never shipped to the
 * client bundle -- this file has no "use client" and is only ever imported by Server
 * Components), forwards the browser's HttpOnly `campaia_session` cookie to the BFF's
 * `GET /me`, and returns the real, session-derived principal or null.
 *
 * The session cookie itself is never readable by client-side JS (HttpOnly) and is never
 * exposed through this function's return value -- only the derived `Me` payload is.
 *
 * The BFF origin is not a secret -- it is the same public origin the browser is directly
 * redirected to for /auth/login -- so a single NEXT_PUBLIC_* variable is used both here
 * (server-side read) and for building browser-facing links, rather than maintaining two
 * variables that could drift apart.
 */
export async function getServerSession(): Promise<Me | null> {
  const bffOrigin = getPublicBffOrigin();
  if (!bffOrigin) {
    return null;
  }

  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get("campaia_session");
  if (!sessionCookie) {
    return null;
  }

  const response = await fetch(`${bffOrigin}/me`, {
    headers: { cookie: `campaia_session=${sessionCookie.value}` },
    cache: "no-store",
  });

  if (!response.ok) {
    return null;
  }

  return (await response.json()) as Me;
}

export function getPublicBffOrigin(): string | undefined {
  return process.env.NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN;
}
