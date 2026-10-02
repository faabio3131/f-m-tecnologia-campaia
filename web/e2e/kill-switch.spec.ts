import { test, expect, type Page } from "@playwright/test";

/**
 * E2E cross-stack REAL do WP-08 (kill switch / parada de emergência) -- reconciliação
 * PR#6, 26/09/2026. Roda contra o mesmo harness real já usado pelos outros specs desta
 * reconciliação (backend Starlette real + Next.js real em build de produção, ver
 * playwright.session.config.ts), nunca um mock de rede.
 *
 * Diferente de WP-06/WP-07: kill switch não passa por fila de aprovação nem exige
 * step-up (decisão de domínio deliberada, ver KillSwitchPanel.tsx) -- por isso este
 * cenário usa um único usuário real, sem um segundo aprovador.
 *
 * A campanha criada aqui fica em DRAFT (a Web atual ainda não tem um botão de
 * "Publicar" -- fora do escopo desta reconciliação, ver comentário em
 * campaigns/[campaignId]/page.tsx). `routes_campaigns.py::kill_switch` trata isso de
 * forma diferente por escopo: TENANT/PLATFORM simplesmente ignoram uma campanha não
 * pausável (sucesso real, 0 afetadas -- mesmo comportamento já coberto por
 * `test_kill_switch_platform_scope_pauses_matching_channel` no backend), enquanto
 * CAMPAIGN levanta um erro real 409 INVALID_STATE (`test_kill_switch_campaign_scope_not_pausable_from_draft`).
 * Este E2E exercita os dois caminhos reais, ponta a ponta, tal como o backend já garante.
 */

const OWNER_TESTID = "test-identity-e2e-test-id-token-tenant-a-owner";

async function loginViaTestHarness(page: Page, testId: string) {
  const responsePromise = page.waitForResponse(
    (r) => r.url().endsWith("/auth/session") && r.request().method() === "POST",
  );
  await page.getByTestId(testId).click();
  await responsePromise;
  await expect(async () => {
    const cookies = await page.context().cookies();
    expect(cookies.some((c) => c.name === "campaia_session")).toBe(true);
  }).toPass({ timeout: 5_000 });
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

test.describe("WP-08: kill switch cross-stack (sem fila de aprovação, sem step-up)", () => {
  test("escopo TENANT pausa o que for pausável (real, ignora rascunhos) e fica auditado", async ({
    page,
  }) => {
    await page.goto("/login");
    await loginViaTestHarness(page, OWNER_TESTID);
    await expect(page).toHaveURL(/\/dashboard/);

    await createCampaignViaUi(page, `WP-08 E2E tenant ${Date.now()}`);

    await page.goto("/settings");
    const killResponse = page.waitForResponse(
      (r) => r.url().endsWith("/kill-switch") && r.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: /parar todas as campanhas deste tenant agora/i })
      .click();
    const result = await killResponse;
    expect(result.status()).toBe(202);
    const body = (await result.json()) as { affected_campaign_ids: string[] };
    // Campanha real criada acima esta em DRAFT -- nao pausavel, ignorada silenciosamente
    // (nao e erro), mesmo comportamento ja coberto no backend real.
    expect(Array.isArray(body.affected_campaign_ids)).toBe(true);
    await expect(page.getByTestId("kill-switch-result-tenant")).toBeVisible();

    // Auditoria real: o contrato exige "ainda assim gera evento e auditoria", mesmo
    // quando nada foi efetivamente pausado.
    const auditResponse = await page.request.get("/api/campaia/audit-events", {
      headers: await sessionCookieHeader(page),
    });
    expect(auditResponse.status()).toBe(200);
    const audit = (await auditResponse.json()) as { items: { action: string }[] };
    expect(audit.items.some((e) => e.action === "KILL_SWITCH")).toBe(true);
  });

  test("escopo CAMPAIGN recusa com 409 INVALID_STATE quando a campanha ainda está em rascunho", async ({
    page,
  }) => {
    await page.goto("/login");
    await loginViaTestHarness(page, OWNER_TESTID);
    await expect(page).toHaveURL(/\/dashboard/);

    const campaignId = await createCampaignViaUi(page, `WP-08 E2E campaign ${Date.now()}`);
    await page.goto(`/campaigns/${campaignId}`);

    const killResponse = page.waitForResponse(
      (r) => r.url().endsWith("/kill-switch") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: /parar esta campanha agora/i }).click();
    const result = await killResponse;
    expect(result.status()).toBe(409);
    expect((await result.json()).code).toBe("INVALID_STATE");

    await expect(
      page.getByText(/não está em um estado que possa ser pausado agora/i),
    ).toBeVisible();
    // Nenhum resultado de sucesso deve aparecer junto com o erro.
    await expect(page.getByTestId("kill-switch-result-campaign")).toHaveCount(0);
  });
});
