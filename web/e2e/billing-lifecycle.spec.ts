import { test, expect } from "@playwright/test";

// Next + Starlette real; deterministic test IdP and fictitious commercial catalog.
// No payment gateway calls, webhook simulation or paid entitlement activation.
test.describe("WP-R02 billing lifecycle", () => {
  test.describe.configure({ retries: 0 });
  test("trial -> cancelar -> solicitar reativacao pendente; outro tenant isolado", async ({ page, browser }) => {
    const origin = "http://127.0.0.1:4174";
    const onboarding = await page.request.post("/api/campaia/onboarding/tenant", {
      headers: { origin, "Idempotency-Key": crypto.randomUUID() },
      data: { id_token: "e2e-test-id-token-billing-owner", company_name: "Billing E2E isolado", segment: "testes" },
    });
    expect(onboarding.status()).toBe(201);
    const { session } = await onboarding.json();
    const created = await page.request.put("/api/campaia/billing/subscription", {
      headers: { origin, "x-csrf-token": session.csrf_token, "x-step-up-token": "test-step-up", "Idempotency-Key": crypto.randomUUID() },
      data: { plan_id: "exemplo-essencial", customer_document: "11144477735", start_trial: true },
    });
    expect(created.status()).toBe(200);
    await page.goto("/billing");
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
    expect((await otherPage.request.get("/api/campaia/billing/subscription")).status()).toBe(404);
    await other.close();
  });
});
