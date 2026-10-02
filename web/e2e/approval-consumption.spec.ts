import { test, expect, type Page } from "@playwright/test";

/**
 * ACHADO 19 (Fase 3 da missão de reconciliação/takeover, 26/09/2026): E2E cross-stack
 * REAL demonstrando que uma ApprovalRequest já usada para aplicar uma mudança real NÃO
 * pode ser reutilizada para autorizar uma segunda mudança independente.
 *
 * FATO CONFIRMADO por execução real nesta sessão (antes da correção): o mesmo
 * approval_id, com uma Idempotency-Key nova, autorizava indefinidamente novas mudanças de
 * orçamento/autonomia sem nova decisão humana -- porque `ApprovalRequest.status` nunca
 * avançava além de APPROVED. Corrigido com um novo estado terminal `APPLIED`
 * (contrato/domínio aditivo) marcado pelos três handlers (patch_budget, publish_campaign,
 * put_autonomy) logo após a mutação real, com o gate de replay por Idempotency-Key movido
 * para antes da checagem de status (replay legítimo da MESMA chave continua funcionando).
 *
 * Este spec cobre o caminho crítico do orçamento (BUDGET_CHANGE) de ponta a ponta pela
 * UI real -- propor, aprovar, aplicar -- e então tenta reaproveitar a MESMA aprovação já
 * usada diretamente contra o backend real (com sessão/CSRF/step-up reais), confirmando a
 * recusa 403 APPROVAL_REQUIRED e que o orçamento real não mudou por causa da tentativa.
 */

const OWNER_TESTID = "test-identity-e2e-test-id-token-tenant-a-owner";
const APPROVER_TESTID = "test-identity-e2e-test-id-token-tenant-a-approver";

async function loginViaTestHarness(page: Page, testId: string) {
  const responsePromise = page.waitForResponse(
    (r) => r.url().endsWith("/auth/session") && r.request().method() === "POST",
  );
  await page.getByTestId(testId).click();
  const response = await responsePromise;
  const body = (await response.json()) as { csrf_token: string };
  await expect(async () => {
    const cookies = await page.context().cookies();
    expect(cookies.some((c) => c.name === "campaia_session")).toBe(true);
  }).toPass({ timeout: 5_000 });
  return { csrfToken: body.csrf_token };
}

async function sessionCookieHeader(page: Page): Promise<Record<string, string>> {
  const cookies = await page.context().cookies();
  const sessionCookie = cookies.find((c) => c.name === "campaia_session");
  return sessionCookie ? { cookie: `campaia_session=${sessionCookie.value}` } : {};
}

test.describe("WP-Fase3 achado 19: consumo de aprovação cross-stack", () => {
  test("uma aprovação de orçamento já aplicada não pode ser reutilizada diretamente contra o backend real", async ({
    page,
  }) => {
    await page.goto("/login");
    const { csrfToken } = await loginViaTestHarness(page, OWNER_TESTID);
    await expect(page).toHaveURL(/\/dashboard/);

    await page.goto("/campaigns");
    await page.getByLabel("Objetivo").fill(`WP-Fase3 achado19 ${Date.now()}`);
    await page.getByLabel("Orçamento total (BRL)").fill("10000");
    await page.getByLabel("Teto diário (BRL)").fill("500");
    const createResponse = page.waitForResponse(
      (r) => r.url().endsWith("/briefs") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: /enviar briefing/i }).click();
    const campaignId = ((await (await createResponse).json()) as { id: string }).id;

    await page.goto(`/campaigns/${campaignId}`);
    await expect(page.getByTestId("budget-daily-cap")).toHaveText("R$ 500,00");

    // Propõe a mudança real via UI.
    await page.getByLabel("Novo orçamento diário").fill("600");
    const proposeResponse = page.waitForResponse(
      (r) => r.url().endsWith("/approvals") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: /propor mudança de orçamento/i }).click();
    const approvalId = ((await (await proposeResponse).json()) as { id: string }).id;

    // Segundo usuário real do mesmo tenant decide o pedido (segregação de funções real).
    const approverContext = await page.context().browser()!.newContext();
    const approverPage = await approverContext.newPage();
    await approverPage.goto("/login");
    await loginViaTestHarness(approverPage, APPROVER_TESTID);
    await approverPage.goto("/approvals");
    const decisionResponse = approverPage.waitForResponse(
      (r) => r.url().endsWith(`/approvals/${approvalId}/decision`),
    );
    await approverPage.getByTestId(`approve-${approvalId}`).click();
    expect((await decisionResponse).status()).toBe(200);
    await approverContext.close();

    // OWNER aplica a mudança já aprovada, via UI real -- orçamento real muda para 600.
    await page.reload();
    await expect(page.getByRole("button", { name: /aplicar alteração/i })).toBeVisible();
    const applyResponse = page.waitForResponse(
      (r) => r.url().endsWith(`/campaigns/${campaignId}/budget`) && r.request().method() === "PATCH",
    );
    await page.getByRole("button", { name: /aplicar alteração/i }).click();
    expect((await applyResponse).status()).toBe(202);
    await expect(page.getByTestId("budget-daily-cap")).toHaveText("R$ 600,00");

    // Confirma, direto contra o backend real, que a aprovação já usada agora está
    // APPLIED -- nunca mais volta a ser interpretada como uma autorização nova.
    const approvalsAfterUse = await page.request.get("/api/campaia/approvals", {
      headers: await sessionCookieHeader(page),
    });
    const approvalAfterUse = ((await approvalsAfterUse.json()) as { id: string; status: string }[]).find(
      (a) => a.id === approvalId,
    );
    expect(approvalAfterUse?.status).toBe("APPLIED");

    // TENTATIVA REAL DE REUSO: mesma aprovação, Idempotency-Key NOVA, direto contra o
    // backend real (sessão/CSRF/step-up reais) -- deve ser recusada, nunca autorizar uma
    // segunda mudança de orçamento independente.
    const reuseAttempt = await page.request.patch(`/api/campaia/campaigns/${campaignId}/budget`, {
      headers: {
        ...(await sessionCookieHeader(page)),
        "x-csrf-token": csrfToken,
        "x-step-up-token": "web-ui-confirmacao-explicita",
        "idempotency-key": `e2e-achado19-reuse-${Date.now()}`.padEnd(16, "x"),
      },
      data: { approval_id: approvalId, new_daily_cap: "700" },
    });
    expect(reuseAttempt.status()).toBe(403);
    const reuseBody = (await reuseAttempt.json()) as { code: string };
    expect(reuseBody.code).toBe("APPROVAL_REQUIRED");

    // O orçamento real não mudou por causa da tentativa de reuso recusada.
    await page.reload();
    await expect(page.getByTestId("budget-daily-cap")).toHaveText("R$ 600,00");
  });
});
