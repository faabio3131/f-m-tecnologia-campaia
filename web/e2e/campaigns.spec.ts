import { expect, test } from "@playwright/test";

test.describe("CampaIA Web /campaigns (WP-05) smoke", () => {
  test("shows the configuration notice when no BFF origin is configured, with no BFF network calls", async ({
    page,
  }) => {
    const bffRequests: string[] = [];
    page.on("request", (request) => {
      // Only fetch/XHR calls can be real BFF calls -- the page's own navigation request to
      // "/campaigns" and Next.js's static chunks/scripts also contain "/campaigns" as a
      // substring and would otherwise false-positive here (unlike e2e/dashboard.spec.ts and
      // e2e/onboarding.spec.ts, whose filters never include their own route's name).
      if (request.resourceType() !== "fetch" && request.resourceType() !== "xhr") return;
      const url = request.url();
      if (/\/(me|briefs|approvals(\/[^/]+\/decision)?|campaigns(\/[^/]+(\/(plan(\/regenerate)?|validate))?)?|auth\/login)\b/.test(url)) {
        bffRequests.push(url);
      }
    });

    await page.goto("/campaigns");

    await expect(page.getByText("Não configurado")).toBeVisible();
    await expect(page.getByText("NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN")).toBeVisible();
    expect(bffRequests).toEqual([]);
  });
});
