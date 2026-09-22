import { expect, test } from "@playwright/test";

test.describe("CampaIA Web /onboarding (WP-04) smoke", () => {
  test("shows the configuration notice when no BFF origin is configured, with no BFF network calls", async ({
    page,
  }) => {
    // Same rationale as e2e/dashboard.spec.ts: this E2E run's production build has no
    // NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN set (matching CI) -- /onboarding must degrade to an
    // honest "not configured" notice rather than crash or silently render as if Brand Kits
    // or connections existed. The real onboarding flow (Brand Kit save, simulated connect)
    // is covered separately by the cross-stack harness (web/playwright.crossstack.config.ts),
    // which needs a live backend this default CI job never runs.
    const bffRequests: string[] = [];
    page.on("request", (request) => {
      if (
        /\/(me|brand-profiles|connections(\/oauth\/(start|complete))?|auth\/login|auth\/callback)\b/.test(
          request.url(),
        )
      ) {
        bffRequests.push(request.url());
      }
    });

    await page.goto("/onboarding");

    await expect(page.getByText("Não configurado")).toBeVisible();
    await expect(page.getByText("NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN")).toBeVisible();
    expect(bffRequests).toEqual([]);
  });
});
