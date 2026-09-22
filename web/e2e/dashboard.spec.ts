import { expect, test } from "@playwright/test";

test.describe("CampaIA Web /dashboard (WP-03) smoke", () => {
  test("shows the configuration notice when no BFF origin is configured, with no BFF network calls", async ({
    page,
  }) => {
    // Same rationale as e2e/account.spec.ts: this E2E run's production build has no
    // NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN set (matching CI) -- /dashboard must degrade to an
    // honest "not configured" notice rather than crash or silently render as if a
    // session/memberships existed. Real login + tenant-switch flows are covered
    // separately by the cross-stack harness (web/playwright.crossstack.config.ts), which
    // needs a live backend this default CI job never runs.
    const bffRequests: string[] = [];
    page.on("request", (request) => {
      if (/\/(me|session\/memberships|session\/switch-tenant|auth\/login|auth\/callback|auth\/logout)\b/.test(request.url())) {
        bffRequests.push(request.url());
      }
    });

    await page.goto("/dashboard");

    await expect(page.getByText("Não configurado")).toBeVisible();
    await expect(page.getByText("NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN")).toBeVisible();
    expect(bffRequests).toEqual([]);
  });
});
