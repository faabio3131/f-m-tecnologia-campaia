import { expect, test } from "@playwright/test";

/**
 * WP-08 cross-stack E2E: emergency stop through a real browser session against a real
 * backend. Unlike every WP-05/06/07 cross-stack spec, this is single-user -- kill switch
 * bypasses the approval queue entirely by domain design (it only ever reduces effect, so
 * there is nothing for a second human to approve).
 *
 * The campaign created here stays DRAFT: nothing in this Web app's UI can move a campaign
 * into a PAUSABLE_STATE (APPROVED/PUBLISHING/ACTIVE/OPTIMIZING) -- publish is deliberately
 * never wired to any screen (see campaigns/[campaignId]/page.tsx's own comment: "nada nesta
 * tela chama POST .../publish"), and this remains true here. So this spec proves the real
 * TENANT-scope path end to end (form -> real POST /kill-switch -> real response rendered)
 * via the one outcome actually reachable through the Web UI today: no campaign affected,
 * because none is in a pausable state -- not a dedicated CAMPAIGN-scope "campaign visibly
 * paused" journey, which the backend session test (test_kill_switch_web_session.py) already
 * covers by reaching APPROVED through the real HTTP flow directly.
 */
test.describe("CampaIA Web kill switch (WP-08) cross-stack E2E", () => {
  test("TENANT scope with no pausable campaigns shows the real empty result", async ({ page }) => {
    await page.goto("/campaigns");
    await page.getByRole("link", { name: "Entrar" }).click();
    await page.getByRole("button", { name: /owner@demo-tenant\.test/ }).click();
    await expect(page).toHaveURL(/\/campaigns$/);
    await page.waitForLoadState("networkidle");

    await page.getByLabel("Objetivo*").fill("Testar kill switch via E2E");
    await page.getByRole("button", { name: "Enviar briefing" }).click();
    await expect(page).toHaveURL(/\/campaigns\/[^/]+$/);
    await page.waitForLoadState("networkidle");

    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: "Parada de emergência" })).toBeVisible();
    await page.getByRole("radio", { name: "Todo o tenant" }).click();
    await page.getByLabel("Motivo").fill("Teste E2E de parada de emergência");
    await page.getByRole("button", { name: "Acionar parada de emergência" }).click();
    await page.waitForLoadState("networkidle");

    await expect(page.getByText(/Escopo TENANT/)).toBeVisible();
    await expect(page.getByText(/nenhuma campanha estava em estado pausável/)).toBeVisible();
  });
});
