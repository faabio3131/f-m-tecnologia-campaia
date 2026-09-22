import { expect, test } from "@playwright/test";

test.describe("CampaIA Web /approvals (WP-05) smoke", () => {
  test("shows the configuration notice when no BFF origin is configured, with no BFF network calls", async ({
    page,
  }) => {
    const bffRequests: string[] = [];
    page.on("request", (request) => {
      // Only fetch/XHR calls can be real BFF calls -- see e2e/campaigns.spec.ts for why the
      // page's own navigation request and Next.js's static chunks are excluded this way.
      if (request.resourceType() !== "fetch" && request.resourceType() !== "xhr") return;
      const url = request.url();
      if (/\/(me|approvals(\/[^/]+\/decision)?)\b/.test(url)) {
        bffRequests.push(url);
      }
    });

    await page.goto("/approvals");

    await expect(page.getByText("Não configurado")).toBeVisible();
    await expect(page.getByText("NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN")).toBeVisible();
    expect(bffRequests).toEqual([]);
  });
});
