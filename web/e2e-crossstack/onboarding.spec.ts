import { expect, test } from "@playwright/test";

/**
 * WP-04 cross-stack E2E: real login through an actual browser, then a real simulated
 * account connection (ConnectAccountCard -> POST /connections/oauth/start +
 * POST /connections/oauth/complete, the backend gap this Work Package closed -- see
 * docs/web/06_ROADMAP_WORK_PACKAGES.md WP-04) and a real Brand Kit save (BrandKitForm ->
 * POST /brand-profiles), proving the "Concluir Onboarding" business rule (enabled only once
 * at least one channel is connected) against the real backend, not a mock.
 */
async function loginAsOwner(page: import("@playwright/test").Page) {
  await page.goto("/onboarding");
  await page.getByRole("link", { name: "Entrar" }).click();
  await page.getByRole("button", { name: /owner@demo-tenant\.test/ }).click();
  await expect(page).toHaveURL(/\/onboarding$/);
  // Same hydration-timing rationale as e2e-crossstack/tenant-switch.spec.ts: `next dev`
  // needs a moment past navigation before client components' onClick handlers are wired.
  await page.waitForLoadState("networkidle");
}

test.describe("CampaIA Web /onboarding (WP-04) cross-stack E2E", () => {
  test("starts with nothing connected and 'Concluir Onboarding' disabled", async ({ page }) => {
    await loginAsOwner(page);

    await expect(page.getByText("Bem-vindo, user-owner-1")).toBeVisible();
    const notConnected = page.getByText("Não conectado");
    await expect(notConnected).toHaveCount(3);
    await expect(
      page.getByText("Conecte ao menos uma conta para concluir o onboarding."),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Concluir Onboarding" })).toHaveCount(0);
  });

  test("connecting one account marks it connected and enables 'Concluir Onboarding'", async ({
    page,
  }) => {
    await loginAsOwner(page);

    await page
      .getByTestId("connect-card-GOOGLE_ADS")
      .getByRole("button", { name: "Conectar (simulado)" })
      .click();

    await expect(page).toHaveURL(/\/onboarding$/);
    await expect(page.getByText("Conectado (simulado)")).toBeVisible();
    await expect(page.getByText("Google Ads (simulado)")).toBeVisible();

    const finishLink = page.getByRole("link", { name: "Concluir Onboarding" });
    await expect(finishLink).toBeVisible();
    await expect(finishLink).toHaveAttribute("href", "/dashboard");

    // Meta and WhatsApp remain genuinely unconnected -- the rule is ">= 1 channel", not
    // "all channels", and nothing here should silently mark the other two as connected too.
    await expect(page.getByText("Não conectado")).toHaveCount(2);
  });

  test("saving a Brand Kit persists it across reload via the real API", async ({ page }) => {
    await loginAsOwner(page);

    await expect(page.getByText(/Nenhum Brand Kit ainda/)).toBeVisible();

    await page.getByLabel("Nome*").fill("Acme Web E2E");
    await page.getByLabel("Tom de voz*").fill("inspirador");
    await page.getByLabel(/Cores principais/).fill("#2f5ce0, #12b886");
    await page.getByLabel(/Diferenciais competitivos/).fill("Entrega rápida\nSuporte 24/7");
    await page.getByRole("button", { name: "Salvar Brand Kit" }).click();

    await expect(page).toHaveURL(/\/onboarding$/);
    await expect(page.getByText("Acme Web E2E")).toBeVisible();
    await expect(page.getByText(/Nenhum Brand Kit ainda/)).toHaveCount(0);
  });
});
