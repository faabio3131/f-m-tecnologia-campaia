import { test, expect } from "@playwright/test";

// Next + Starlette real; deterministic test IdP and fictitious commercial catalog.
// No payment gateway calls, webhook simulation or paid entitlement activation.
test.describe("WP-R02 billing lifecycle", () => {
  test.describe.configure({ retries: 0 });
  test("trial -> cancelar -> solicitar reativacao pendente; outro tenant isolado", async ({ page, browser }) => {
    await page.goto("/login");
    // Browser fetch uses the actual HttpOnly/Secure cookie protocol, as product UI does.
    // APIRequestContext on HTTP loopback does not send this Secure session cookie.
    const onboarding = await page.evaluate(async () => {
      const response = await fetch("/api/campaia/onboarding/tenant", {
        method: "POST", credentials: "include",
        headers: { "content-type": "application/json", "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ id_token: "e2e-test-id-token-billing-owner", company_name: "Billing E2E isolado", segment: "testes" }),
      });
      return { status: response.status, body: await response.json() };
    });
    expect(onboarding.status).toBe(201);
    await page.goto("/billing");
    await page.getByLabel("Plano", { exact: true }).selectOption("exemplo-essencial");
    await page.getByLabel("CPF ou CNPJ do titular").fill("11144477735");
    await page.getByLabel("Iniciar período de teste de 7 dias").check();
    await page.getByRole("button", { name: "Revisar contratação" }).click();
    const subscriptionResponse = page.waitForResponse((response) =>
      response.url().endsWith("/billing/subscription") && response.request().method() === "PUT");
    await page.getByRole("button", { name: "Confirmar contratação" }).click();
    expect((await subscriptionResponse).status()).toBe(200);
    await expect(page.getByRole("region", { name: "Assinatura atual" })).toBeVisible();
    await expect(page.getByText("Liberado", { exact: true })).toBeVisible();
    // Existing billing API emits a SIMULATOR charge only in this explicit test harness.
    const chargeStatus = await page.evaluate(async (csrf: string) => {
      const response = await fetch("/api/campaia/billing/charges", {
        method: "POST", credentials: "include",
        headers: { "content-type": "application/json", "x-csrf-token": csrf, "x-step-up-token": "test-step-up", "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ competence: "2026-10" }),
      });
      return response.status;
    }, onboarding.body.session.csrf_token);
    expect(chargeStatus).toBe(202);
    await page.goto("/billing");
    await expect(page.getByText("Simulação", { exact: true })).toBeVisible();
    await expect(page.getByText("Pendente", { exact: true })).toBeVisible();
    await expect(page.getByRole("article").getByText("R$ 1,00", { exact: true })).toBeVisible();
    await expect(page.getByText("Período de teste", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Liberado", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Cancelar assinatura", exact: true }).click();
    await expect(page.getByText("Cancelada", { exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Confirmar alteração" }).click();
    await expect(page.getByText("Cancelada", { exact: true })).toBeVisible();
    await expect(page.getByText("Bloqueado", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Solicitar reativação", exact: true }).click();
    await page.getByRole("button", { name: "Confirmar alteração" }).click();
    await expect(page.getByText("Aguardando pagamento", { exact: true })).toBeVisible();
    await expect(page.getByText("Bloqueado", { exact: true })).toBeVisible();
    await page.reload();
    await expect(page.getByText("Aguardando pagamento confirmado", { exact: true })).toBeVisible();
    await page.screenshot({ path: "test-results/billing-desktop.png", fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: "test-results/billing-mobile.png", fullPage: true });

    const other = await browser.newContext();
    const otherPage = await other.newPage();
    await otherPage.goto("/login");
    await otherPage.getByTestId("test-identity-e2e-test-id-token-tenant-b-owner").click();
    await expect(otherPage).toHaveURL(/\/dashboard/);
    await otherPage.goto("/billing");
    await expect(otherPage.getByText("Nenhuma assinatura configurada", { exact: true })).toBeVisible();
    expect(await otherPage.evaluate(async () => (await fetch("/api/campaia/billing/subscription", { credentials: "include" })).status)).toBe(404);
    const isolatedHistory = await otherPage.evaluate(async () => (await fetch("/api/campaia/billing/charges", { credentials: "include" })).json());
    expect(isolatedHistory.items).toEqual([]);
    await other.close();
  });
});
