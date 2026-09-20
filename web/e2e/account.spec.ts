import { expect, test } from "@playwright/test";

test.describe("CampaIA Web /account (WP-02) smoke", () => {
  test("shows the configuration notice when no BFF origin is configured, with no BFF network calls", async ({
    page,
  }) => {
    // This E2E run's production build has no NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN set (matching
    // CI, which never configures a live backend for the frontend job) -- /account must
    // degrade to an honest "not configured" notice rather than crash or silently render
    // as if a session existed.
    const bffRequests: string[] = [];
    page.on("request", (request) => {
      if (/\/(me|auth\/login|auth\/callback|auth\/logout)\b/.test(request.url())) {
        bffRequests.push(request.url());
      }
    });

    await page.goto("/account");

    await expect(page.getByText("Não configurado")).toBeVisible();
    await expect(
      page.getByText("NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN"),
    ).toBeVisible();
    expect(bffRequests).toEqual([]);
  });
});
