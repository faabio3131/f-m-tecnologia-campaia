import { expect, test, type BrowserContext } from "@playwright/test";

/**
 * WP-06 cross-stack E2E: budget change through two real, independent browser sessions
 * against the same real backend -- same two-context pattern as
 * e2e-crossstack/briefing-approval-journey.spec.ts (WP-05). Reuses the existing /approvals
 * queue entirely for the decision step; this spec only exercises the propose (BudgetPanel on
 * /campaigns/[id]) and apply steps that are new in this Work Package.
 */
test.describe("CampaIA Web budget change (WP-06) cross-stack E2E", () => {
  test("propose -> approve (separate user) -> apply, budget reflects the real change", async ({
    page,
    browser,
  }) => {
    await page.goto("/campaigns");
    await page.getByRole("link", { name: "Entrar" }).click();
    await page.getByRole("button", { name: /owner@demo-tenant\.test/ }).click();
    await expect(page).toHaveURL(/\/campaigns$/);
    await page.waitForLoadState("networkidle");

    await page.getByLabel("Objetivo*").fill("Testar alteração de orçamento via E2E");
    await page.getByRole("button", { name: "Enviar briefing" }).click();
    await expect(page).toHaveURL(/\/campaigns\/[^/]+$/);
    await page.waitForLoadState("networkidle");

    // BriefForm's default daily_cap is 1000 -- propose +10% (1100), safely within the
    // domain's default max_change_pct (20%). exact:true avoids ambiguity: "BRL 1000" is
    // also a substring of "BRL 10000" (total_amount) and of the combined briefMeta text.
    await expect(page.getByText("BRL 1000", { exact: true })).toBeVisible();
    await page.getByLabel("Propor novo teto diário").fill("1100");
    await page.getByRole("button", { name: "Propor alteração" }).click();
    await expect(page).toHaveURL(/\/campaigns\/[^/]+$/);
    await page.waitForLoadState("networkidle");
    await expect(page.getByText(/aguardando aprovação/)).toBeVisible();

    const campaignUrl = page.url();
    const campaignId = campaignUrl.split("/").pop();

    // A genuinely distinct logged-in user, a SEPARATE real browser session against the same
    // backend, decides it on the existing /approvals queue -- no new decision UI for WP-06.
    // /approvals lists every approval for the tenant, and by the time this spec runs
    // alongside briefing-approval-journey.spec.ts (same shared backend, sequential workers),
    // an unrelated PUBLISH approval may already be APPROVED there too -- data-testid scopes
    // this test to its own BUDGET_CHANGE card specifically, avoiding a strict-mode ambiguity
    // on a bare "APPROVED" text match.
    const approverContext: BrowserContext = await browser.newContext({ ignoreHTTPSErrors: true });
    const approverPage = await approverContext.newPage();
    await approverPage.goto("/approvals");
    await approverPage.getByRole("link", { name: "Entrar" }).click();
    await approverPage.getByRole("button", { name: /approver@demo-tenant\.test/ }).click();
    await expect(approverPage).toHaveURL(/\/approvals$/);
    await approverPage.waitForLoadState("networkidle");

    const budgetCard = approverPage.getByTestId(`approval-card-BUDGET_CHANGE-${campaignId}`);
    await budgetCard.getByRole("button", { name: "Aprovar" }).click();
    await approverPage.waitForLoadState("networkidle");
    await expect(budgetCard.getByText("APPROVED")).toBeVisible();
    await approverContext.close();

    // Back on the proposer's own session: the approved-but-unapplied change is visible, and
    // applying it makes the real budget change.
    await page.goto(campaignUrl);
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Novo teto diário aprovado: BRL 1100.")).toBeVisible();
    await page.getByRole("button", { name: "Aplicar alteração" }).click();
    await page.waitForLoadState("networkidle");

    await expect(page.getByText("BRL 1100", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Aplicar alteração" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Propor alteração" })).toBeVisible();
  });
});
