import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next 16 auto-generates AGENTS.md/CLAUDE.md into the project root on `next dev` unless
  // disabled -- unwanted here (WP-01's own scope is "no lint/tooling config beyond what
  // Next.js's own generator produces"; agent-instruction files are a separate concern this
  // repo already manages at its own root, not per-package).
  agentRules: false,
  // Dev-mode-only guard (has no effect on `next build`/`next start`): the WP-03
  // cross-stack E2E harness (web/playwright.crossstack.config.ts) runs `next dev` on
  // 127.0.0.1, which Next 16 otherwise blocks HMR/client-bundle requests from by default
  // ("Blocked cross-origin request to Next.js dev resource"). Without this, hydration
  // silently never completes and client components (LogoutButton, TenantSwitcher) never
  // attach their event handlers.
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
