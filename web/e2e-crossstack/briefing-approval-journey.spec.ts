import { expect, test, type BrowserContext, type Page } from "@playwright/test";

/**
 * WP-05 cross-stack E2E: the full critical journey (briefing -> estratégia (IA) ->
 * validação -> fila de aprovação) through two real, independent browser sessions against
 * the same real backend -- proposer (`owner`, one BrowserContext/cookie jar) and approver
 * (`approver`, a SECOND BrowserContext/cookie jar), proving segregation of duties end-to-end
 * with a real browser, not just the backend-level proof in
 * tests_api/test_briefing_approval_web_session.py. `owner` is used as proposer (not
 * `marketer`) for the same reason as that backend test: OWNER holds APPROVAL_DECIDE, so its
 * own self-approval attempt is rejected specifically by segregation of duties, not by a
 * simple missing-permission denial.
 */
async function loginAs(page: Page, email: RegExp) {
  await page.goto("/campaigns");
  await page.getByRole("link", { name: "Entrar" }).click();
  await page.getByRole("button", { name: email }).click();
  await expect(page).toHaveURL(/\/campaigns$/);
  await page.waitForLoadState("networkidle");
}

test.describe("CampaIA Web briefing -> aprovação (WP-05) cross-stack E2E", () => {
  test("full journey: brief -> estratégia -> validação -> aprovação, self-approval rejected, distinct approver accepts", async ({
    page,
    browser,
  }) => {
    await loginAs(page, /owner@demo-tenant\.test/);

    // 1. Submit the brief.
    await page.getByLabel("Objetivo*").fill("Gerar leads qualificados para o novo tênis");
    await page.getByRole("button", { name: "Enviar briefing" }).click();
    await expect(page).toHaveURL(/\/campaigns\/[^/]+$/);
    await page.waitForLoadState("networkidle");

    // 2. Generate the strategy.
    await expect(
      page.getByText("Nenhuma estratégia gerada ainda para esta campanha."),
    ).toBeVisible();
    await page.getByRole("button", { name: "Gerar estratégia" }).click();
    await expect(page).toHaveURL(/\/campaigns\/[^/]+$/);
    await page.waitForLoadState("networkidle");
    await expect(page.getByText(/Versão 1 — gerado por/)).toBeVisible();

    // 3. Validate.
    await page.getByRole("button", { name: "Validar" }).click();
    await expect(page.getByText("APPROVABLE")).toBeVisible();

    // 4. Request approval.
    await page.getByRole("button", { name: "Solicitar aprovação" }).click();
    await expect(page).toHaveURL(/\/campaigns\/[^/]+$/);
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: "Validar" }).click();
    await expect(page.getByText("Aprovação já solicitada — aguardando decisão.")).toBeVisible();

    // 5. Same proposer, on the real approval queue, tries to decide their own proposal --
    // rejected visibly (roadmap WP-05 acceptance criterion).
    await page.goto("/approvals");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: "Aprovar" }).click();
    await expect(
      page.getByText("Você não pode decidir sobre a sua própria proposta."),
    ).toBeVisible();

    // 6. A genuinely distinct logged-in user, a SEPARATE real browser session against the
    // same backend, decides it -- accepted.
    const approverContext: BrowserContext = await browser.newContext({
      ignoreHTTPSErrors: true,
    });
    const approverPage = await approverContext.newPage();
    await approverPage.goto("/approvals");
    await approverPage.getByRole("link", { name: "Entrar" }).click();
    await approverPage.getByRole("button", { name: /approver@demo-tenant\.test/ }).click();
    await expect(approverPage).toHaveURL(/\/approvals$/);
    await approverPage.waitForLoadState("networkidle");

    await approverPage.getByRole("button", { name: "Aprovar" }).click();
    await expect(approverPage).toHaveURL(/\/approvals$/);
    await approverPage.waitForLoadState("networkidle");
    await expect(approverPage.getByText("APPROVED")).toBeVisible();
    await expect(
      approverPage.getByRole("button", { name: "Aprovar" }),
    ).toHaveCount(0);

    await approverContext.close();

    // 7. The proposer's own queue, reloaded, reflects the real decision made by the
    // approver's separate session.
    await page.reload();
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("APPROVED")).toBeVisible();
  });
});
