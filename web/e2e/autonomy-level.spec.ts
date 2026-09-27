import { test, expect, type Page } from "@playwright/test";

/**
 * E2E cross-stack REAL do WP-07 (nível de autonomia) -- reconciliação PR#6, 26/09/2026.
 * Roda contra o mesmo harness real já usado por session-protocol.spec.ts e
 * budget-change.spec.ts (backend Starlette real + Next.js real em build de produção,
 * ver playwright.session.config.ts), nunca um mock de rede.
 *
 * Autonomia é configuração de TENANT (não de campanha) -- o painel vive em `/settings`
 * (AutonomyPanel.tsx). `POST /approvals` ainda exige um `campaign_id` real mesmo para
 * `AUTONOMY_CHANGE` (restrição já existente do CURRENT, ver comentário em
 * AutonomyPanel.tsx), por isso este teste também cria uma campanha real antes de propor
 * a mudança.
 *
 * A configuração padrão do tenant de demonstração tem `level = max_level_allowed =
 * APROVADO (1)` (campaia_core/autonomy.py::DEFAULT_LEVEL/AutonomySettings) -- não há
 * espaço para SUBIR de nível sem alterar o teto (`max_level_allowed`), que não tem
 * endpoint de escrita no contrato atual (fora do escopo desta Web). Por isso o cenário
 * de ponta a ponta aqui desce o nível (APROVADO -> ASSISTENTE, nível 0), a única mudança
 * de estado real possível sob a configuração padrão. A recusa de subir acima do teto
 * (guarda anti-autopromoção I-11) já é coberta por
 * `backend/tests_api/test_smoke_endpoints.py::test_autonomy_get_and_put` -- não
 * duplicada aqui.
 *
 * ACHADO REAL descoberto construindo este E2E, registrado em
 * docs/evidence/RECONCILIACAO_TAKEOVER_FINAL_20260926.md (fora do escopo desta Web para
 * corrigir sozinha): nenhum `ApprovalRequest` é marcado como "consumido" depois de um
 * `PUT /autonomy` (nem depois de `PATCH /campaigns/{id}/budget`) real -- o registro
 * continua com `status: APPROVED` para sempre, então uma segunda carga da página
 * encontra a MESMA aprovação já usada e oferece "aplicar" de novo. Isso significa que
 * dois cenários de nível de autonomia no MESMO tenant, em sequência, colidem: o segundo
 * encontraria a aprovação já consumida do primeiro em vez de propor uma nova. Por isso
 * este arquivo usa DOIS tenants reais e independentes (tenant A no cenário feliz, tenant
 * B no cenário negativo) -- nunca dois cenários de autonomia no mesmo tenant -- em vez de
 * mascarar o achado com um reset de estado artificial.
 */

const OWNER_A_TESTID = "test-identity-e2e-test-id-token-tenant-a-owner";
const APPROVER_A_TESTID = "test-identity-e2e-test-id-token-tenant-a-approver";
const OWNER_B_TESTID = "test-identity-e2e-test-id-token-tenant-b-owner";

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

test.describe("WP-07: nível de autonomia cross-stack", () => {
  test("propor -> aprovar -> aplicar, com o nível real exibido mudando (dois usuários reais, tenant A)", async ({
    browser,
  }) => {
    const ownerContext = await browser.newContext();
    const ownerPage = await ownerContext.newPage();
    await ownerPage.goto("/login");
    await loginViaTestHarness(ownerPage, OWNER_A_TESTID);
    await expect(ownerPage).toHaveURL(/\/dashboard/);

    // Autonomia exige uma campanha-ancora real no tenant (ver nota do arquivo).
    await createCampaignViaUi(ownerPage, `WP-07 E2E ancora ${Date.now()}`);

    await ownerPage.goto("/settings");
    await expect(ownerPage.getByTestId("autonomy-level-label")).toHaveText("APROVADO");

    await ownerPage.getByLabel("Novo nível (0 a 3)").fill("0");
    const proposeResponse = ownerPage.waitForResponse(
      (r) => r.url().endsWith("/approvals") && r.request().method() === "POST",
    );
    await ownerPage.getByRole("button", { name: /propor mudança de nível/i }).click();
    const proposed = (await (await proposeResponse).json()) as { id: string };
    await expect(ownerPage.getByText(/pedido de mudança de nível pendente/i)).toBeVisible();

    // Segundo usuario real, MESMO tenant, contexto de navegador totalmente separado --
    // decide o pedido na fila de Aprovacoes real (WP-05, inalterado).
    const approverContext = await browser.newContext();
    const approverPage = await approverContext.newPage();
    await approverPage.goto("/login");
    await loginViaTestHarness(approverPage, APPROVER_A_TESTID);
    await expect(approverPage).toHaveURL(/\/dashboard/);

    await approverPage.goto("/approvals");
    const decisionResponse = approverPage.waitForResponse(
      (r) => r.url().endsWith(`/approvals/${proposed.id}/decision`),
    );
    await approverPage.getByTestId(`approve-${proposed.id}`).click();
    expect((await decisionResponse).status()).toBe(200);

    // OWNER volta a Configuracoes e aplica a mudanca ja aprovada.
    await ownerPage.reload();
    await expect(ownerPage.getByRole("button", { name: /aplicar nível de autonomia/i })).toBeVisible();
    const applyResponse = ownerPage.waitForResponse(
      (r) => r.url().endsWith("/autonomy") && r.request().method() === "PUT",
    );
    await ownerPage.getByRole("button", { name: /aplicar nível de autonomia/i }).click();
    expect((await applyResponse).status()).toBe(200);

    // Nivel real exibido muda de APROVADO para ASSISTENTE.
    await expect(ownerPage.getByTestId("autonomy-level-label")).toHaveText("ASSISTENTE");

    await ownerContext.close();
    await approverContext.close();
  });

  test("autoaprovação recusada e aplicação sem step-up recusada (tenant B, isolado do cenário feliz)", async ({
    browser,
  }) => {
    const ownerContext = await browser.newContext();
    const ownerPage = await ownerContext.newPage();
    await ownerPage.goto("/login");
    await loginViaTestHarness(ownerPage, OWNER_B_TESTID);
    await expect(ownerPage).toHaveURL(/\/dashboard/);

    await createCampaignViaUi(ownerPage, `WP-07 E2E self-approve ${Date.now()}`);
    await ownerPage.goto("/settings");
    await expect(ownerPage.getByTestId("autonomy-level-label")).toHaveText("APROVADO");
    await ownerPage.getByLabel("Novo nível (0 a 3)").fill("0");
    const proposeResponse = ownerPage.waitForResponse(
      (r) => r.url().endsWith("/approvals") && r.request().method() === "POST",
    );
    await ownerPage.getByRole("button", { name: /propor mudança de nível/i }).click();
    const proposed = (await (await proposeResponse).json()) as { id: string };

    // Segregacao de funcoes: o proprio OWNER (quem propos) tenta decidir a propria
    // proposta na fila real -- a UI nunca esconde o botao, o backend real recusa.
    await ownerPage.goto("/approvals");
    await ownerPage.getByTestId(`approve-${proposed.id}`).click();
    await expect(ownerPage.getByText(/não foi possível decidir/i)).toBeVisible();

    // Nivel ainda nao mudou (nenhuma autoaprovacao indevida teve efeito de dominio).
    await ownerPage.goto("/settings");
    await expect(ownerPage.getByTestId("autonomy-level-label")).toHaveText("APROVADO");

    // Step-up: PUT /autonomy real, com sessao/CSRF validos mas SEM o header de step-up --
    // o backend real recusa com 403 STEP_UP_REQUIRED mesmo com approval_id de uma
    // aprovacao real (ainda PENDING, o que sozinho ja bastaria para recusar, mas o gate
    // de step-up roda antes de qualquer lookup de aprovacao em routes_autonomy.py).
    //
    // SECURITY FIX (27/09/2026 -- correcao final pre-Google-Ads): esta checagem precisa
    // de uma sessao SEM nenhum step-up persistido ainda -- `ownerPage` ja nao serve mais,
    // porque a tentativa de autoaprovacao acima (clique real na UI de Aprovacoes) ja
    // enviou um X-Step-Up-Token genuino (STEP_UP_HEADER em approvals/page.tsx) e,
    // corretamente, esse step-up agora permanece valido por ate' STEP_UP_MAX_AGE
    // (10 min) -- reusar `ownerPage` aqui testaria uma sessao que JA tem step-up, nao a
    // ausencia dele. Um segundo contexto/login do MESMO OWNER, que nunca passou por
    // nenhuma acao com step-up, prova a exigencia real.
    const freshOwnerContext = await browser.newContext();
    const freshOwnerPage = await freshOwnerContext.newPage();
    await freshOwnerPage.goto("/login");
    const { body: freshOwnerLogin } = await loginViaTestHarness(freshOwnerPage, OWNER_B_TESTID);

    const noStepUpResponse = await freshOwnerPage.request.put("/api/campaia/autonomy", {
      data: { level: 0, approval_id: proposed.id },
      headers: {
        ...(await sessionCookieHeader(freshOwnerPage)),
        "x-csrf-token": freshOwnerLogin.csrf_token,
        "idempotency-key": `e2e-no-step-up-autonomy-${Date.now()}`,
      },
    });
    expect(noStepUpResponse.status()).toBe(403);
    expect((await noStepUpResponse.json()).code).toBe("STEP_UP_REQUIRED");

    await freshOwnerContext.close();
    await ownerContext.close();
  });
});
