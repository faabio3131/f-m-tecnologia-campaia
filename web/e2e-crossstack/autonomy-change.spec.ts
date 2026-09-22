import { expect, test, type BrowserContext } from "@playwright/test";

/**
 * WP-07 cross-stack E2E: autonomy level change through two real, independent browser
 * sessions against the same real backend -- same two-context pattern as
 * e2e-crossstack/budget-change.spec.ts (WP-06). Reuses the existing /approvals queue
 * entirely for the decision step; this spec only exercises the propose (AutonomyPanel on
 * /dashboard) and apply steps that are new in this Work Package.
 *
 * create_approval still requires a campaign_id even for a tenant-wide AUTONOMY_CHANGE
 * (real backend constraint, documented in docs/web/06_ROADMAP_WORK_PACKAGES.md's WP-07
 * section) -- the propose form is disabled until at least one campaign exists, so this
 * spec creates one via the existing /campaigns briefing flow first, purely to satisfy
 * that constraint, then does the actual autonomy work on /dashboard.
 */
test.describe("CampaIA Web autonomy change (WP-07) cross-stack E2E", () => {
  test("propose -> approve (separate user) -> apply, level reflects the real change", async ({
    page,
    browser,
  }) => {
    await page.goto("/campaigns");
    await page.getByRole("link", { name: "Entrar" }).click();
    await page.getByRole("button", { name: /owner@demo-tenant\.test/ }).click();
    await expect(page).toHaveURL(/\/campaigns$/);
    await page.waitForLoadState("networkidle");

    await page.getByLabel("Objetivo*").fill("Testar alteração de autonomia via E2E");
    await page.getByRole("button", { name: "Enviar briefing" }).click();
    await expect(page).toHaveURL(/\/campaigns\/[^/]+$/);
    await page.waitForLoadState("networkidle");
    const campaignId = page.url().split("/").pop();

    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");

    // CURRENT default: level=1 (APROVADO), max_level_allowed=1 -- the only in-ceiling
    // change available is lowering to level 0 (ASSISTENTE).
    await expect(page.getByText("Nível de autonomia")).toBeVisible();
    await page.getByRole("radio", { name: /0 — ASSISTENTE/ }).click();
    await page.getByRole("button", { name: "Propor alteração" }).click();
    await page.waitForLoadState("networkidle");
    await expect(page.getByText(/aguardando aprovação/)).toBeVisible();

    // A genuinely distinct logged-in user, a SEPARATE real browser session against the same
    // backend, decides it on the existing /approvals queue -- no new decision UI for WP-07.
    // data-testid scopes this test to its own AUTONOMY_CHANGE card specifically, avoiding a
    // strict-mode ambiguity if other approvals exist on the shared backend.
    const approverContext: BrowserContext = await browser.newContext({ ignoreHTTPSErrors: true });
    const approverPage = await approverContext.newPage();
    await approverPage.goto("/approvals");
    await approverPage.getByRole("link", { name: "Entrar" }).click();
    await approverPage.getByRole("button", { name: /approver@demo-tenant\.test/ }).click();
    await expect(approverPage).toHaveURL(/\/approvals$/);
    await approverPage.waitForLoadState("networkidle");

    const autonomyCard = approverPage.getByTestId(`approval-card-AUTONOMY_CHANGE-${campaignId}`);
    await autonomyCard.getByRole("button", { name: "Aprovar" }).click();
    await approverPage.waitForLoadState("networkidle");
    await expect(autonomyCard.getByText("APPROVED")).toBeVisible();
    await approverContext.close();

    // Back on the proposer's own session: the approved-but-unapplied change is visible, and
    // applying it makes the real level change.
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Novo nível aprovado: 0.")).toBeVisible();
    await page.getByRole("button", { name: "Aplicar alteração" }).click();
    await page.waitForLoadState("networkidle");

    const summary = page.getByText("Nível atual").locator("..");
    await expect(summary.getByText("0 — ASSISTENTE")).toBeVisible();
    await expect(page.getByRole("button", { name: "Aplicar alteração" })).toHaveCount(0);
  });
});
