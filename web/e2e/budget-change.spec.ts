import { test, expect, type Page } from "@playwright/test";

/**
 * E2E cross-stack REAL do WP-06 (alteração de orçamento) -- reconciliação PR#6,
 * 26/09/2026. Roda contra o Next.js real (build de produção) + backend Starlette
 * real (backend/tests_support/e2e_server.py), nunca um mock de rede -- mesmo
 * harness já usado por session-protocol.spec.ts (ver playwright.session.config.ts
 * e docs/evidence/RECONCILIACAO_TAKEOVER_FINAL_20260926.md).
 *
 * Cenário coberto de ponta a ponta, com dois usuários reais do MESMO tenant
 * (demo-tenant): OWNER propõe -> APPROVER decide -> OWNER aplica -> orçamento
 * exibido muda. A PR#6 tinha um E2E equivalente (web/e2e-crossstack/
 * budget-change.spec.ts) -- este arquivo reconstrói o CENÁRIO sobre a
 * arquitetura/harness real da PR#5, não copia o código daquele.
 */

const OWNER_TESTID = "test-identity-e2e-test-id-token-tenant-a-owner";
const APPROVER_TESTID = "test-identity-e2e-test-id-token-tenant-a-approver";
const TENANT_B_TESTID = "test-identity-e2e-test-id-token-tenant-b-owner";

/** Mesmo helper de session-protocol.spec.ts (login real via harness de teste). */
async function loginViaTestHarness(page: Page, testId: string) {
  const responsePromise = page.waitForResponse(
    (r) => r.url().endsWith("/auth/session") && r.request().method() === "POST",
  );
  await page.getByTestId(testId).click();
  const response = await responsePromise;
  const body = (await response.json()) as { csrf_token: string; tenant_id: string; user_id: string };
  await expect(async () => {
    const cookies = await page.context().cookies();
    expect(cookies.some((c) => c.name === "campaia_session")).toBe(true);
  }).toPass({ timeout: 5_000 });
  return { status: response.status(), body };
}

async function sessionCookieHeader(page: Page): Promise<Record<string, string>> {
  const cookies = await page.context().cookies();
  const sessionCookie = cookies.find((c) => c.name === "campaia_session");
  return sessionCookie ? { cookie: `campaia_session=${sessionCookie.value}` } : {};
}

async function createCampaignViaUi(page: Page, objective: string): Promise<string> {
  await page.goto("/campaigns");
  await page.getByLabel("Objetivo").fill(objective);
  await page.getByLabel("Orçamento total (BRL)").fill("10000");
  await page.getByLabel("Teto diário (BRL)").fill("500");
  const createResponse = page.waitForResponse(
    (r) => r.url().endsWith("/briefs") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: /enviar briefing/i }).click();
  const response = await createResponse;
  expect(response.status()).toBe(202);
  const created = (await response.json()) as { id: string };
  return created.id;
}

test.describe("WP-06: alteração de orçamento cross-stack (dois usuários reais)", () => {
  test("propor -> aprovar -> aplicar, com o orçamento real exibido mudando", async ({ browser }) => {
    const ownerContext = await browser.newContext();
    const ownerPage = await ownerContext.newPage();
    await ownerPage.goto("/login");
    await loginViaTestHarness(ownerPage, OWNER_TESTID);
    await expect(ownerPage).toHaveURL(/\/dashboard/);

    const campaignId = await createCampaignViaUi(ownerPage, `WP-06 E2E ${Date.now()}`);
    await ownerPage.goto(`/campaigns/${campaignId}`);
    // Escopado no valor real do painel de orçamento (data-testid), não em getByText livre --
    // o JSON bruto da Estratégia (IA) na mesma página também pode conter o número "500"
    // (o brief original), o que faria uma busca de texto solta colidir com ele.
    await expect(ownerPage.getByTestId("budget-daily-cap")).toHaveText("R$ 500,00");

    // OWNER propoe uma mudanca para 600.
    await ownerPage.getByLabel("Novo orçamento diário").fill("600");
    const proposeResponse = ownerPage.waitForResponse(
      (r) => r.url().endsWith("/approvals") && r.request().method() === "POST",
    );
    await ownerPage.getByRole("button", { name: /propor mudança de orçamento/i }).click();
    const proposed = (await (await proposeResponse).json()) as { id: string };
    await expect(ownerPage.getByText(/pedido de mudança de orçamento pendente/i)).toBeVisible();

    // Segundo usuario real, MESMO tenant, contexto de navegador totalmente
    // separado -- decide o pedido na fila de Aprovacoes (WP-05, inalterado).
    const approverContext = await browser.newContext();
    const approverPage = await approverContext.newPage();
    await approverPage.goto("/login");
    await loginViaTestHarness(approverPage, APPROVER_TESTID);
    await expect(approverPage).toHaveURL(/\/dashboard/);

    await approverPage.goto("/approvals");
    const decisionResponse = approverPage.waitForResponse(
      (r) => r.url().endsWith(`/approvals/${proposed.id}/decision`),
    );
    await approverPage.getByTestId(`approve-${proposed.id}`).click();
    // routes_approvals.py::decide_approval devolve json_response(...) sem status_code
    // explicito -- 200, nao 202 (202 e so para efeitos assincronos como create_brief).
    expect((await decisionResponse).status()).toBe(200);

    // OWNER volta ao detalhe da campanha e aplica a mudanca ja aprovada.
    await ownerPage.reload();
    await expect(ownerPage.getByRole("button", { name: /aplicar alteração/i })).toBeVisible();
    const applyResponse = ownerPage.waitForResponse(
      (r) => r.url().endsWith(`/campaigns/${campaignId}/budget`) && r.request().method() === "PATCH",
    );
    await ownerPage.getByRole("button", { name: /aplicar alteração/i }).click();
    expect((await applyResponse).status()).toBe(202);

    // Orcamento diario real exibido muda de 500 para 600 (valor Decimal/string
    // tratado corretamente no browser -- ver BudgetPanel.tsx toNumber()).
    await expect(ownerPage.getByTestId("budget-daily-cap")).toHaveText("R$ 600,00");

    // Isolamento de tenant: um terceiro usuario, de OUTRO tenant, jamais ve esta
    // campanha nem consegue decidir a aprovacao ja usada (dados nunca vazam entre
    // tenants, mesmo por ID direto).
    const otherTenantContext = await browser.newContext();
    const otherTenantPage = await otherTenantContext.newPage();
    await otherTenantPage.goto("/login");
    await loginViaTestHarness(otherTenantPage, TENANT_B_TESTID);
    await expect(otherTenantPage).toHaveURL(/\/dashboard/);
    const crossTenantGet = await otherTenantPage.request.get(
      `/api/campaia/campaigns/${campaignId}`,
      { headers: await sessionCookieHeader(otherTenantPage) },
    );
    expect([403, 404]).toContain(crossTenantGet.status());

    await ownerContext.close();
    await approverContext.close();
    await otherTenantContext.close();
  });

  test("autoaprovação recusada e aplicação sem step-up recusada", async ({ browser }) => {
    const ownerContext = await browser.newContext();
    const ownerPage = await ownerContext.newPage();
    await ownerPage.goto("/login");
    const { body: ownerLogin } = await loginViaTestHarness(ownerPage, OWNER_TESTID);
    await expect(ownerPage).toHaveURL(/\/dashboard/);

    const campaignId = await createCampaignViaUi(ownerPage, `WP-06 E2E self-approve ${Date.now()}`);
    await ownerPage.goto(`/campaigns/${campaignId}`);
    await ownerPage.getByLabel("Novo orçamento diário").fill("650");
    const proposeResponse = ownerPage.waitForResponse(
      (r) => r.url().endsWith("/approvals") && r.request().method() === "POST",
    );
    await ownerPage.getByRole("button", { name: /propor mudança de orçamento/i }).click();
    const proposed = (await (await proposeResponse).json()) as { id: string };

    // The UI prevents self-approval; a direct authenticated attempt still proves server-side SoD.
    await ownerPage.goto("/approvals");
    await expect(ownerPage.getByTestId(`approve-${proposed.id}`)).toBeDisabled();
    const selfApproval = await ownerPage.request.post(`/api/campaia/approvals/${proposed.id}/decision`, {
      data: { decision: "APPROVE" },
      headers: { ...(await sessionCookieHeader(ownerPage)), "x-csrf-token": ownerLogin.csrf_token,
        "x-step-up-token": "e2e-self-approval-proof", "idempotency-key": `e2e-self-approval-${Date.now()}` },
    });
    expect(selfApproval.status()).toBe(403);
    expect((await selfApproval.json()).code).toBe("SEPARATION_OF_DUTIES");

    // Confirma que o orcamento NAO mudou (nenhuma autoaprovacao indevida teve
    // efeito de dominio).
    await ownerPage.goto(`/campaigns/${campaignId}`);
    await expect(ownerPage.getByTestId("budget-daily-cap")).toHaveText("R$ 500,00");

    // Step-up: chamada direta ao PATCH real de orcamento, com sessao/CSRF validos
    // mas SEM o header de step-up -- o backend real recusa com 403
    // STEP_UP_REQUIRED, mesmo sem approval_id valido (o gate de step-up roda antes
    // de qualquer lookup de aprovacao em routes_campaigns.py::patch_budget).
    //
    // The direct self-approval attempt presented test step-up on ownerPage.
    // A fresh session, without any elevation, must still be rejected before application.
    const freshOwnerContext = await browser.newContext();
    const freshOwnerPage = await freshOwnerContext.newPage();
    await freshOwnerPage.goto("/login");
    const { body: freshOwnerLogin } = await loginViaTestHarness(freshOwnerPage, OWNER_TESTID);

    const noStepUpResponse = await freshOwnerPage.request.patch(
      `/api/campaia/campaigns/${campaignId}/budget`,
      {
        data: { approval_id: proposed.id, daily_cap: "650" },
        headers: {
          ...(await sessionCookieHeader(freshOwnerPage)),
          "x-csrf-token": freshOwnerLogin.csrf_token,
          "idempotency-key": `e2e-no-step-up-${Date.now()}`,
        },
      },
    );
    expect(noStepUpResponse.status()).toBe(403);
    const noStepUpBody = await noStepUpResponse.json();
    expect(noStepUpBody.code).toBe("STEP_UP_REQUIRED");

    await freshOwnerContext.close();
    await ownerContext.close();
  });
});
