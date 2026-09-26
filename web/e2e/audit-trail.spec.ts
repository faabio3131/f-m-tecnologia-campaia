import { test, expect, type Page } from "@playwright/test";

/**
 * E2E cross-stack REAL do WP-10 (trilha de auditoria) -- reconciliação PR#6, 26/09/2026.
 * Roda contra o mesmo harness real já usado pelos outros specs desta reconciliação
 * (backend Starlette real + Next.js real em build de produção, ver
 * playwright.session.config.ts), nunca um mock de rede.
 *
 * `GET /audit-events` já existia (usado internamente por vários WPs anteriores para
 * registrar suas próprias ações) -- este é o primeiro E2E que efetivamente LÊ a trilha
 * pela Web, então o caminho crítico aqui é: uma ação real de outro WP (kill switch,
 * WP-08 -- escolhido por não precisar de fila de aprovação nem de um segundo usuário,
 * mantendo o cenário simples) gera um evento real, e a tela `/audit` real mostra esse
 * evento, incluindo sua evidência real.
 */

const TENANT_A_TESTID = "test-identity-e2e-test-id-token-tenant-a-owner";

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

test.describe("WP-10: trilha de auditoria cross-stack", () => {
  test("uma ação real de outro WP aparece na trilha real, com sua evidência", async ({ page }) => {
    await page.goto("/login");
    await loginViaTestHarness(page, TENANT_A_TESTID);
    await expect(page).toHaveURL(/\/dashboard/);

    // Gera um evento real e reconhecível (WP-08, ja reconciliado): kill switch de
    // escopo TENANT, sem fila de aprovacao, sem step-up -- caminho mais simples para
    // produzir um evento de auditoria real sem depender de um segundo usuario.
    await page.goto("/settings");
    const killResponse = page.waitForResponse(
      (r) => r.url().endsWith("/kill-switch") && r.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: /parar todas as campanhas deste tenant agora/i })
      .click();
    expect((await killResponse).status()).toBe(202);

    // A trilha real de auditoria mostra esse evento -- nao um mock, nao um evento
    // fabricado pela UI: o mesmo GET /audit-events que o backend ja usa internamente.
    const auditResponsePromise = page.waitForResponse(
      (r) => r.url().endsWith("/audit-events") && r.request().method() === "GET",
    );
    await page.goto("/audit");
    const auditResponse = await auditResponsePromise;
    expect(auditResponse.status()).toBe(200);
    const audit = (await auditResponse.json()) as {
      items: { action: string; evidence: Record<string, unknown> | null }[];
    };
    const killSwitchEvent = audit.items.find((e) => e.action === "KILL_SWITCH");
    expect(killSwitchEvent).toBeTruthy();

    await expect(page.getByText("KILL_SWITCH").first()).toBeVisible();
    // A evidencia real (scope/reason/affected) e exibida, nao escondida.
    await expect(page.getByText(/"scope":\s*"TENANT"/).first()).toBeVisible();
  });

  test("filtra a trilha por campanha via a UI real", async ({ page }) => {
    await page.goto("/login");
    await loginViaTestHarness(page, TENANT_A_TESTID);
    await expect(page).toHaveURL(/\/dashboard/);

    await page.goto("/campaigns");
    await page.getByLabel("Objetivo").fill(`WP-10 E2E filtro ${Date.now()}`);
    await page.getByLabel("Orçamento total (BRL)").fill("10000");
    await page.getByLabel("Teto diário (BRL)").fill("500");
    const createResponse = page.waitForResponse(
      (r) => r.url().endsWith("/briefs") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: /enviar briefing/i }).click();
    const created = (await (await createResponse).json()) as { id: string };

    await page.goto("/audit");
    await expect(page.getByText("CAMPAIGN_CREATE").first()).toBeVisible();

    const filteredResponsePromise = page.waitForResponse(
      (r) => r.url().includes(`/audit-events?campaign_id=${created.id}`) && r.request().method() === "GET",
    );
    await page.getByLabel(/id da campanha/i).fill(created.id);
    await page.getByRole("button", { name: /^filtrar$/i }).click();
    const filteredResponse = await filteredResponsePromise;
    expect(filteredResponse.status()).toBe(200);
    const filtered = (await filteredResponse.json()) as { items: { target: string }[] };
    expect(filtered.items.every((e) => e.target === created.id)).toBe(true);
    expect(filtered.items.length).toBeGreaterThan(0);
  });
});
