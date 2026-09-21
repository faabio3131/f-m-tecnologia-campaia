import { cookies } from "next/headers";
import type {
  ApprovalRequest,
  AutonomySettings,
  BrandProfile,
  Campaign,
  CampaignPlan,
  Connection,
  Me,
  SessionMemberships,
} from "@/contracts/types";

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

/** WP-05: the tenant's campaigns (GET /campaigns). Empty array is a real, valid state (no
 * brief submitted yet) -- only null means the read itself failed. Unwraps the contract's
 * {items, next_cursor} envelope -- there is no real pagination layer yet (see
 * routes_campaigns.py's own comment on `next_cursor` always being null), so callers just
 * want the list. */
export async function getServerCampaigns(): Promise<Campaign[] | null> {
  const envelope = await getWithSessionCookie<{ items: Campaign[] }>("/campaigns");
  return envelope ? envelope.items : null;
}

/** WP-05: a single campaign's detail (GET /campaigns/{id}), reconciled state included. Null
 * covers both "read failed" and "not found" -- callers show the same not-found-shaped UI
 * either way, exactly like BrandKitForm/ConnectAccountCard already do for other reads. */
export async function getServerCampaign(campaignId: string): Promise<Campaign | null> {
  return getWithSessionCookie<Campaign>(`/campaigns/${encodeURIComponent(campaignId)}`);
}

/** WP-05: a campaign's current plan (GET /campaigns/{id}/plan). `plan: null` inside the
 * response is a real, valid state (no strategy generated yet) -- only the outer null means
 * the read itself failed. */
export async function getServerPlan(campaignId: string): Promise<CampaignPlan | null> {
  return getWithSessionCookie<CampaignPlan>(`/campaigns/${encodeURIComponent(campaignId)}/plan`);
}

/** WP-05: pending approvals for the tenant (GET /approvals). Empty array is a real, valid
 * state (nothing awaiting decision) -- only null means the read itself failed. */
export async function getServerApprovals(): Promise<ApprovalRequest[] | null> {
  return getWithSessionCookie<ApprovalRequest[]>("/approvals");
}

/** WP-07: the tenant's current autonomy level and contracted ceiling (GET /autonomy).
 * Always resolves to a real settings object server-side (backend seeds a default) -- only
 * null means the read itself failed. */
export async function getServerAutonomy(): Promise<AutonomySettings | null> {
  return getWithSessionCookie<AutonomySettings>("/autonomy");
}

export function getPublicBffOrigin(): string | undefined {
  return process.env.NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN;
}
