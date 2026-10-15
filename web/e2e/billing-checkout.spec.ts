import { test, expect } from "@playwright/test";

test("duas abas revisam a mesma obrigação e emitem uma cobrança simulada sem liberar acesso pago", async ({ page, context }) => {
  await page.goto("/login");
  const onboard = await page.evaluate(async () => {
    const response = await fetch("/api/campaia/onboarding/tenant", { method: "POST", credentials: "include",
      headers: { "content-type": "application/json", "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ id_token: "e2e-test-id-token-billing-owner", company_name: "Checkout E2E", segment: "testes" }) });
    return response.status;
  });
  expect(onboard).toBe(201);
  await page.goto("/billing");
  await page.getByLabel("Plano", { exact: true }).selectOption("e2e-commercial");
  await page.getByLabel("CPF ou CNPJ do titular").fill("11144477735");
  await page.getByLabel("Iniciar período de teste de 7 dias").uncheck();
  await page.getByRole("button", { name: "Revisar contratação" }).click();
  await page.getByRole("button", { name: "Confirmar contratação" }).click();
  await expect(page.getByText("Aguardando pagamento", { exact: true })).toBeVisible();
  await expect(page.getByText("Bloqueado", { exact: true })).toBeVisible();
  await expect(page.getByText("Simulação: esta cobrança não movimenta dinheiro.")).toBeVisible();
  const second = await context.newPage();
  await second.goto("/billing");
  for (const tab of [page, second]) {
    await tab.getByRole("button", { name: "Revisar e emitir cobrança" }).click();
    await expect(tab.getByRole("button", { name: "Confirmar cobrança" })).toBeDisabled();
    await tab.getByRole("checkbox", { name: /Conferi o plano/ }).check();
  }
  const before = await page.evaluate(async () => (await fetch("/api/campaia/billing/charges")).json());
  expect(before.items).toHaveLength(0);
  const responses = [page, second].map(tab => tab.waitForResponse(response =>
    response.url().endsWith("/billing/charges") && response.request().method() === "POST"));
  await Promise.all([page, second].map(tab => tab.getByRole("button", { name: "Confirmar cobrança" }).click()));
  for (const response of await Promise.all(responses)) expect(response.status()).toBe(202);
  for (const tab of [page, second]) {
    await expect(tab.getByText("Cobrança registrada. O acesso muda somente após confirmação do pagamento.")).toBeVisible();
    await expect(tab.getByText("Bloqueado", { exact: true })).toBeVisible();
  }
  const after = await page.evaluate(async () => (await fetch("/api/campaia/billing/charges")).json());
  expect(after.items).toHaveLength(1);
  expect(Number(after.items[0].amount)).toBe(12.5);
  expect(after.items[0].gateway_mode).toBe("SIMULATOR");
  await second.close();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/checkout-mobile.png", fullPage: true });
});
