import { expect, test } from "@playwright/test";

/**
 * WP-10 cross-stack E2E: the real audit trail through a real browser session against a
 * real backend. Connects an account (a real action WP-04's own flow already proves end to
 * end) and confirms the resulting real events (OAUTH_START, CONNECTION_CREATE) show up on
 * /audit -- not a fabricated or mocked list, the actual trail the backend recorded.
 */
test.describe("CampaIA Web audit trail (WP-10) cross-stack E2E", () => {
  test("a real action elsewhere in the app shows up in the real audit trail", async ({ page }) => {
    await page.goto("/onboarding");
    await page.getByRole("link", { name: "Entrar" }).click();
    await page.getByRole("button", { name: /owner@demo-tenant\.test/ }).click();
    await expect(page).toHaveURL(/\/onboarding$/);
    await page.waitForLoadState("networkidle");

    // WHATSAPP stays genuinely unconnected across this file's other specs (only
    // GOOGLE_ADS/META are used elsewhere in this cross-stack suite) -- avoids the same
    // shared-backend-state pollution already root-caused for WP-09 (P-34).
    await page
      .getByTestId("connect-card-WHATSAPP")
      .getByRole("button", { name: "Conectar (simulado)" })
      .click();
    await expect(page).toHaveURL(/\/onboarding$/);
    await expect(
      page.getByTestId("connect-card-WHATSAPP").getByText("Conectado (simulado)"),
    ).toBeVisible();

    await page.goto("/audit");
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: "Trilha de auditoria" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "OAUTH_START" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "CONNECTION_CREATE" })).toBeVisible();
    // The real actor is the logged-in user, never fabricated.
    await expect(page.getByText(/USER — user-owner-1/).first()).toBeVisible();

    // This file's backend process is shared with every other cross-stack spec
    // (workers: 1) -- leaving WHATSAPP connected here pollutes onboarding.spec.ts's own
    // "nothing connected yet" and "exactly one connected" assertions, which run later in
    // the same alphabetically-ordered suite. Disconnect it before the test ends, the same
    // hygiene WP-09's own spec already applies to itself.
    await page.goto("/onboarding");
    await page.waitForLoadState("networkidle");
    await page
      .getByTestId("connect-card-WHATSAPP")
      .getByRole("button", { name: "Desconectar" })
      .click();
    await expect(page).toHaveURL(/\/onboarding$/);
    await expect(
      page.getByTestId("connect-card-WHATSAPP").getByText("Não conectado"),
    ).toBeVisible();
  });
});
