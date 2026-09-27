import { test, expect, type Page } from "@playwright/test";

/**
 * E2E cross-stack REAL do WP-11 (métricas honestas) -- reconciliação PR#6, 26/09/2026.
 * Roda contra o mesmo harness real já usado pelos outros specs desta reconciliação
 * (backend Starlette real + Next.js real em build de produção, ver
 * playwright.session.config.ts), nunca um mock de rede.
 *
 * O caminho crítico aqui é o inverso do habitual: confirmar que a Web NÃO fabrica
 * dados quando o backend real ainda não tem uma camada de analytics -- uma campanha
 * recém-criada nunca teve eventos reais sincronizados, então `GET
 * /campaigns/{id}/insights` real sempre devolve `points: []` e a nota honesta do
 * backend, nunca um gráfico ou número inventado pela Web.
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

test.describe("WP-11: métricas honestas cross-stack", () => {
  test("campanha real sem analytics mostra a nota honesta do backend, nunca dados inventados", async ({
    page,
  }) => {
    await page.goto("/login");
    await loginViaTestHarness(page, TENANT_A_TESTID);
    await expect(page).toHaveURL(/\/dashboard/);

    await page.goto("/campaigns");
    await page.getByLabel("Objetivo").fill(`WP-11 E2E métricas ${Date.now()}`);
    await page.getByLabel("Orçamento total (BRL)").fill("10000");
    await page.getByLabel("Teto diário (BRL)").fill("500");
    const createResponse = page.waitForResponse(
      (r) => r.url().endsWith("/briefs") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: /enviar briefing/i }).click();
    const created = (await (await createResponse).json()) as { id: string };

    const insightsResponsePromise = page.waitForResponse(
      (r) => r.url().endsWith(`/campaigns/${created.id}/insights`) && r.request().method() === "GET",
    );
    await page.goto(`/campaigns/${created.id}`);
    const insightsResponse = await insightsResponsePromise;
    expect(insightsResponse.status()).toBe(200);
    const insights = (await insightsResponse.json()) as {
      points: unknown[];
      note: string;
    };
    // FATO CONFIRMADO (execução real, achado 15): o backend real não tem camada de
    // analytics ainda -- uma campanha recém-criada sempre tem `points: []`.
    expect(insights.points).toEqual([]);
    expect(insights.note.length).toBeGreaterThan(0);

    // A Web mostra a nota real do backend -- nunca um placeholder genérico, nunca um
    // gráfico ou número fabricado.
    await expect(page.getByText(insights.note)).toBeVisible();
  });
});
