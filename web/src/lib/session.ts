import { cookies } from "next/headers";
import type { BrandProfile, Connection, Me, SessionMemberships } from "@/contracts/types";

/**
 * WP-02: server-only, session-cookie-authenticated GET. Runs on the Next.js server (never
 * shipped to the client bundle -- this file has no "use client" and is only ever imported
 * by Server Components), forwards the browser's HttpOnly `campaia_session` cookie to the
 * BFF, and returns the parsed JSON or null on any failure (missing config, no session, BFF
 * error) -- callers must not distinguish those cases beyond what the null already means.
 *
 * The session cookie itself is never readable by client-side JS (HttpOnly) and is never
 * exposed through any of this file's return values -- only the derived JSON payloads are.
 */
async function getWithSessionCookie<T>(path: string): Promise<T | null> {
  const bffOrigin = getPublicBffOrigin();
  if (!bffOrigin) {
    return null;
  }

  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get("campaia_session");
  if (!sessionCookie) {
    return null;
  }

  const response = await fetch(`${bffOrigin}${path}`, {
    headers: { cookie: `campaia_session=${sessionCookie.value}` },
    cache: "no-store",
  });

  if (!response.ok) {
    return null;
  }

  return (await response.json()) as T;
}

export async function getServerSession(): Promise<Me | null> {
  return getWithSessionCookie<Me>("/me");
}

/**
 * WP-03: the session's real tenant memberships (GET /session/memberships). A real session
 * always has at least its own active tenant, so an empty result is impossible here -- null
 * means the read itself failed, never "no memberships".
 */
export async function getServerSessionMemberships(): Promise<SessionMemberships | null> {
  return getWithSessionCookie<SessionMemberships>("/session/memberships");
}

/** WP-04: the tenant's Brand Kits (GET /brand-profiles). Empty array is a real, valid
 * state (no Brand Kit created yet) -- only null means the read itself failed. */
export async function getServerBrandProfiles(): Promise<BrandProfile[] | null> {
  return getWithSessionCookie<BrandProfile[]>("/brand-profiles");
}

/** WP-04: the tenant's connected accounts (GET /connections). Empty array is a real, valid
 * state (nothing connected yet) -- only null means the read itself failed. */
export async function getServerConnections(): Promise<Connection[] | null> {
  return getWithSessionCookie<Connection[]>("/connections");
}

export function getPublicBffOrigin(): string | undefined {
  return process.env.NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN;
}
