import { expect, test } from "@playwright/test";

/**
 * WP-11 cross-stack E2E: the real, honest metrics placeholder through a real browser
 * session against a real backend. Submits a brief (the same real flow WP-05's own spec
 * already proves end to end) and confirms the campaign detail page's "Métricas" section
 * shows the real note GET /campaigns/{id}/insights returns -- never a fabricated chart or
 * an invented empty state.
 */
test.describe("CampaIA Web campaign insights (WP-11) cross-stack E2E", () => {
  test("a freshly created campaign shows the real, honest empty-metrics note", async ({
    page,
  }) => {
    await page.goto("/campaigns");
    await page.getByRole("link", { name: "Entrar" }).click();
    await page.getByRole("button", { name: /owner@demo-tenant\.test/ }).click();
    await expect(page).toHaveURL(/\/campaigns$/);
    await page.waitForLoadState("networkidle");

    await page.getByLabel("Objetivo*").fill("Testar métricas honestas via E2E");
    await page.getByRole("button", { name: "Enviar briefing" }).click();
    await expect(page).toHaveURL(/\/campaigns\/[^/]+$/);
    await page.waitForLoadState("networkidle");

    // exact:true avoids ambiguity: the brief's own title text ("Testar métricas honestas via
    // E2E") also contains the substring "métricas", which Playwright's default
    // case-insensitive substring match would otherwise pick up as a second "heading" match.
    await expect(page.getByRole("heading", { name: "Métricas", exact: true })).toBeVisible();
    // The real note from campaia_core/routes_campaigns.py's honest placeholder -- never a
    // chart, a zero, or a Web-invented "sem dados" string.
    await expect(
      page.getByText(/No analytics layer implemented yet in campaia_core/),
    ).toBeVisible();
  });
});
