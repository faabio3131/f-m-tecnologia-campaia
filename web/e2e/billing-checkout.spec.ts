import { test, expect } from "@playwright/test";

test("duas abas emitem uma fatura; pagamento simulado, uso e fechamento final preservam cada ciclo", async ({ page, context }) => {
  await page.goto("/login");
  const onboard = await page.evaluate(async () => {
    const response = await fetch("/api/campaia/onboarding/tenant", { method: "POST", credentials: "include",
      headers: { "content-type": "application/json", "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ id_token: "e2e-test-id-token-billing-owner", company_name: "Checkout E2E", segment: "testes" }) });
    const body = await response.json();
    return { status: response.status, csrf: body.session.csrf_token as string };
  });
  expect(onboard.status).toBe(201);
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
  await page.setViewportSize({ width: 1280, height: 900 });
  // Authenticated callbacks for the payment SIMULATOR, not external banking evidence.
  const consumed = await page.evaluate(async ({ csrf, paymentId, amount }) => {
    const headers = { "content-type": "application/json", "x-csrf-token": csrf,
      "x-step-up-token": "test-step-up", "Idempotency-Key": crypto.randomUUID() };
    const post = async (path: string, body: unknown) => {
      const response = await fetch(`/api/campaia${path}`, { method: "POST", credentials: "include",
        headers: { ...headers, "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify(body) });
      if (!response.ok) throw new Error(`${path}: ${response.status}`);
      return response.json();
    };
    const paid = await fetch("/api/campaia/webhooks/asaas", { method: "POST",
      headers: { "content-type": "application/json", "asaas-access-token": "fixture-checkout-webhook" },
      body: JSON.stringify({ id: "e2e-first-paid", event: "PAYMENT_RECEIVED", payment: { id: paymentId, status: "RECEIVED", value: amount } }) });
    if (!paid.ok) throw new Error(`payment: ${paid.status}`);
    const usage = await (await fetch("/api/campaia/billing/usage")).json();
    await post("/billing/usage/consent", { cap: "5.00", cycle_id: usage.cycle.id,
      policy_version: usage.cycle.policy_version, extra_credit_price: usage.balance.extra_credit_price });
    const campaign = await post("/briefs", { objective: "Sell shoes", product: "Shoes", audience: "Runners",
      region: "BR", currency: "BRL", total_budget: "5000", daily_cap: "500", channels: ["GOOGLE_ADS"] });
    for (let index = 0; index < 3; index++) {
      const quote = await (await fetch(`/api/campaia/campaigns/${campaign.id}/plan/quote`)).json();
      await post(`/campaigns/${campaign.id}/plan/regenerate`, { credit_confirmation: {
        cycle_id: quote.cycle_id, policy_version: quote.policy_version, credits: quote.credits, extra_amount: quote.extra_amount } });
    }
    return (await fetch("/api/campaia/billing/usage")).json();
  }, { csrf: onboard.csrf, paymentId: after.items[0].gateway_charge_id, amount: after.items[0].amount });
  expect(consumed.balance.consumed_credits).toBe(15);
  expect(Number(consumed.balance.extra_consumed_amount)).toBe(5);
  await page.reload();
  await page.getByRole("button", { name: "Encerrar imediatamente", exact: true }).click();
  await page.getByRole("button", { name: "Confirmar solicitação", exact: true }).click();
  await expect(page.getByText("Cancelada", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Revisar fechamento final" }).click();
  await page.getByRole("checkbox", { name: /Conferi o consumo final/ }).check();
  await page.getByRole("button", { name: "Confirmar fechamento final", exact: true }).click();
  await expect(page.getByText(/Fatura final registrada no histórico/)).toBeVisible();
  const finalHistory = await page.evaluate(async () => (await fetch("/api/campaia/billing/charges")).json());
  expect(finalHistory.items).toHaveLength(2);
  const finalInvoice = finalHistory.items.find((item: { purpose: string }) => item.purpose === "FINAL_USAGE");
  expect(Number(finalInvoice.amount)).toBe(5);
  const settled = await page.evaluate(async ({ paymentId, amount }: { paymentId: string; amount: string }) => (await fetch("/api/campaia/webhooks/asaas", {
    method: "POST", headers: { "content-type": "application/json", "asaas-access-token": "fixture-checkout-webhook" },
    body: JSON.stringify({ id: "e2e-final-paid", event: "PAYMENT_RECEIVED", payment: { id: paymentId, status: "RECEIVED", value: amount } }),
  })).status, { paymentId: finalInvoice.gateway_charge_id, amount: String(finalInvoice.amount) });
  expect(settled).toBe(200);
  await page.getByRole("button", { name: "Atualizar fechamento", exact: true }).click();
  await expect(page.getByText(/Excedente final quitado/)).toBeVisible();
  await expect(page.getByText("Cancelada", { exact: true })).toBeVisible();
  await expect(page.getByText("Bloqueado", { exact: true })).toBeVisible();
  const finalUsage = await page.evaluate(async () => (await fetch("/api/campaia/billing/usage")).json());
  expect(finalUsage.cycle.id).toBe(consumed.cycle.id);
  expect(finalUsage.balance.consumed_credits).toBe(15);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/final-usage-mobile.png", fullPage: true });

  // A guarantee request covers verified payments but does not dispatch or claim a refund.
  await page.getByRole("button", { name: "Atualizar garantia", exact: true }).click();
  const guarantee = await page.evaluate(async () => (await fetch("/api/campaia/billing/guarantee")).json());
  expect(guarantee.state).toBe("ELIGIBLE");
  expect(guarantee.items).toHaveLength(2);
  expect(Number(guarantee.paid_amount)).toBe(17.5);
  await page.getByRole("button", { name: "Revisar solicitação de garantia", exact: true }).click();
  await expect(page.getByRole("button", { name: "Confirmar solicitação de garantia", exact: true })).toBeDisabled();
  await page.getByRole("checkbox", { name: /acesso pago será encerrado imediatamente/ }).check();
  await page.getByRole("button", { name: "Confirmar solicitação de garantia", exact: true }).click();
  await expect(page.getByText(/recebimento do pedido não confirma o estorno/)).toBeVisible();
  const afterGuarantee = await page.evaluate(async () => ({
    guarantee: await (await fetch("/api/campaia/billing/guarantee")).json(),
    usage: await (await fetch("/api/campaia/billing/usage")).json(),
    charges: await (await fetch("/api/campaia/billing/charges")).json(),
  }));
  expect(afterGuarantee.guarantee.state).toBe("REQUESTED");
  expect(afterGuarantee.usage.access_active).toBe(false);
  expect(afterGuarantee.usage.balance.consumed_credits).toBe(15);
  expect(afterGuarantee.charges.items).toHaveLength(2);
  expect(afterGuarantee.charges.items.every((item: { gateway_refund_state: string | null }) => item.gateway_refund_state === null)).toBe(true);
  await expect(page.getByText("Cancelada", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/guarantee-request-mobile.png", fullPage: true });

});
