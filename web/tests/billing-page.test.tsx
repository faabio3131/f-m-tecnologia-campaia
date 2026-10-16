import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import BillingPage from "@/app/(app)/(authenticated)/billing/page";
import type { BillingPlan, BillingSubscription } from "@/contracts/types";
import { setCsrfToken } from "@/lib/api/client";

const context = vi.hoisted(() => ({ tenant: "a", roles: ["OWNER"], ready: true }));
vi.mock("@/providers/AuthProvider", () => ({ useAuth: () => ({ session: { tenant_id: context.tenant, user_id: "owner" }, me: { roles: context.roles } }) }));
vi.mock("@/hooks/useAdministrativeStepUp", () => ({ useAdministrativeStepUp: () => ({ ready: context.ready, testMode: true, headers: () => ({ "x-step-up-token": "fresh-proof" }), consumePresentedToken: vi.fn(), noteError: vi.fn(), onIdToken: vi.fn(), stepUpMessage: null }) }));
const plan: BillingPlan = {
  fingerprint: "a".repeat(64),
  plan_id: "test-basic", name: "Plano contratado", currency: "BRL", monthly_price: "12.50",
  included_credits: "30", extra_credit_unit_price: "0.10", trial_days: 7,
  cancellation_mode: "IMMEDIATE", reactivation_mode: "PAYMENT_REQUIRED",
  reactivation_billing_mode: "CURRENT_PLAN_FULL_CYCLE",
  plan_changes: [{ target_plan_id: "test-pro", kind: "UPGRADE", billing_mode: "TARGET_PLAN_FULL_CYCLE" }],
};
const sub: BillingSubscription = {
  tenant_id: "a", customer_ref: "a", customer_document: "11144477735", plan_id: plan.plan_id,
  plan_name: plan.name, status: "ACTIVE", commercial_terms: plan,
  entitlement_access_active: true, entitlements: { max_users: 2, max_active_campaigns: 4, channels: ["GOOGLE_ADS"], ai_capabilities: [], resources: [] },
};
function response(status: number, data: unknown) { return Promise.resolve(new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json" } })); }
function mockRead(subscription: unknown = sub, status = 200, catalogStatus = 200) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    if (String(input).endsWith("/billing/guarantee")) return response(200, { state: "UNAVAILABLE", fingerprint: null, first_paid_at: null, deadline: null, paid_amount: null, currency: "BRL", items: [], request_id: null, requested_at: null });
    if (String(input).endsWith("/billing/charges")) return response(200, { items: [], next_cursor: null });
    if (String(input).endsWith("/billing/subscription")) return response(status, subscription);
    if (String(input).endsWith("/billing/plans")) return response(catalogStatus, { items: [{ ...plan, monthly_price: "99.00" }, { ...plan, plan_id: "test-pro", name: "Plano Pro" }] });
    throw new Error(`Unexpected ${input}`);
  });
}
beforeEach(() => { context.tenant = "a"; context.roles = ["OWNER"]; context.ready = true; setCsrfToken("csrf"); });
afterEach(() => { vi.restoreAllMocks(); setCsrfToken(null); });

describe("Billing Web", () => {
  it("preserves one checkout and its confirmation when history and subscription refresh together", async () => {
    const user = userEvent.setup();
    const current: BillingSubscription = { ...sub, status: "PENDING_PAYMENT", entitlement_access_active: false,
      activated_at: null, cancel_at_period_end: null, pending_plan_id: null,
      commercial_terms: { ...plan, credit_policy: { version: "test-v1", trial_credits: 30,
        trial_max_users: 1, trial_max_active_campaigns: 1, action_weights: { strategy: 5 } } } };
    const quote = { organization_name: "Teste", holder_document_masked: "***7735", fingerprint: "b".repeat(64),
      billing_id: "fixture", competence: "cycle:0", amount: "12.50", currency: "BRL", plan_id: plan.plan_id,
      plan_name: plan.name, included_credits: 10, extra_credit_price: "1.00", action_weights: [], policy_version: "test-v1",
      purpose: "REGULAR", cycle_index: 0, due_at: "2026-10-15T03:00:00Z", period_starts_at: null, period_ends_at: null,
      lines: [{ description: "Mensalidade", amount: "12.50" }], provider: "SIMULATOR", mode: "SIMULATOR" };
    let emitted = false;
    const consoleError = vi.spyOn(console, "error");
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/billing/charges") && init?.method === "POST") { emitted = true; return response(202, {}); }
      if (url.endsWith("/billing/charges")) return response(200, { items: [], next_cursor: null });
      if (url.endsWith("/billing/subscription")) return response(200, current);
      if (url.endsWith("/billing/plans")) return response(200, { items: [plan] });
      if (url.endsWith("/billing/guarantee")) return response(200, { state: "UNAVAILABLE", fingerprint: null, first_paid_at: null, deadline: null, paid_amount: null, currency: "BRL", items: [], request_id: null, requested_at: null });
      if (url.endsWith("/billing/usage")) return response(200, { availability: "UNAVAILABLE", access_active: false, can_authorize_extras: false, cycle: null, balance: null, alerts: [], actions: [] });
      if (url.endsWith("/billing/checkout")) return response(200, { state: emitted ? "REGISTERED" : "READY", quote, available_at: null, invoice_url: null });
      throw new Error(`Unexpected ${url}`);
    });
    render(<BillingPage />);
    await user.click(await screen.findByRole("button", { name: "Revisar e emitir cobrança" }));
    await user.click(screen.getByRole("checkbox", { name: /Conferi o plano/ }));
    await user.click(screen.getByRole("button", { name: "Confirmar cobrança" }));
    await screen.findByText("Cobrança registrada. O acesso muda somente após confirmação do pagamento.");
    await screen.findByText("Cobrança já registrada. Consulte a fatura e o histórico.");
    expect(screen.getAllByRole("heading", { name: "Pagamento da assinatura" })).toHaveLength(1);
    expect(consoleError.mock.calls.some(args => args.some(value => /same key/i.test(String(value))))).toBe(false);
  });

  it("mostra condicoes contratadas distintas do catalogo, limites e consumo indisponivel", async () => {
    const fetch = mockRead(); render(<BillingPage />);
    expect(within(await screen.findByRole("region", { name: "Assinatura atual" })).getByText("R$ 12,50")).toBeInTheDocument();
    expect(screen.getByText("R$ 99,00")).toBeInTheDocument();
    expect(await screen.findByText("Medição de consumo ainda indisponível")).toBeInTheDocument();
    expect(screen.queryByText(sub.customer_document)).not.toBeInTheDocument();
    expect(fetch.mock.calls.every(([, init]) => init?.method === "GET")).toBe(true);
  });
  it("distingue assinatura ausente de acesso negado", async () => {
    mockRead({ code: "NOT_FOUND" }, 404); render(<BillingPage />);
    expect(await screen.findByText("Nenhuma assinatura configurada")).toBeInTheDocument();
  });
  it("nao mostra catalogo nem acoes quando consulta da assinatura e negada", async () => {
    mockRead({ code: "PERMISSION_DENIED" }, 403); render(<BillingPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível consultar");
    expect(screen.queryByRole("button", { name: "Cancelar assinatura" })).not.toBeInTheDocument();
  });
  it("preserva assinatura quando catalogo esta indisponivel", async () => {
    mockRead(sub, 200, 503); render(<BillingPage />);
    expect(within(await screen.findByRole("region", { name: "Assinatura atual" })).getByText("R$ 12,50")).toBeInTheDocument();
    expect(screen.getByText("Catálogo de planos indisponível")).toBeInTheDocument();
  });
  it("mostra atraso, carencia e acesso conforme resposta do servidor", async () => {
    mockRead({ ...sub, status: "PAST_DUE", entitlement_access_active: false, grace_period_ends_at: "2026-10-20T00:00:00Z", past_due_in_grace: true });
    render(<BillingPage />);
    expect(await screen.findByText("Bloqueado")).toBeInTheDocument();
    expect(screen.getByText("Dentro da carência")).toBeInTheDocument();
    expect(screen.getByText("Sim")).toBeInTheDocument();
  });
  it("esconde mutacoes para papel somente de leitura", async () => {
    context.roles = ["ADMIN"]; mockRead(); render(<BillingPage />);
    await screen.findByText("Assinatura atual");
    expect(screen.queryByRole("button", { name: "Cancelar assinatura" })).not.toBeInTheDocument();
  });
  it("exige step-up antes da confirmacao", async () => {
    context.ready = false; mockRead(); const user = userEvent.setup(); render(<BillingPage />);
    await user.click(await screen.findByRole("button", { name: "Cancelar assinatura" }));
    expect(screen.getByRole("button", { name: "Confirmar alteração" })).toBeDisabled();
  });
  it("confirma cancelamento, preserva chave no retry e envia CSRF/step-up", async () => {
    const read = mockRead(); const user = userEvent.setup();
    let attempts = 0; const headers: Headers[] = [];
    const impl = read.getMockImplementation()!;
    read.mockImplementation((input, init) => {
      if (init?.method === "POST") {
        headers.push(new Headers(init.headers)); attempts++;
        if (attempts === 1) return Promise.reject(new TypeError("network"));
        return response(200, { ...sub, status: "CANCELED", entitlement_access_active: false });
      }
      return impl(input, init);
    });
    render(<BillingPage />);
    await user.click(await screen.findByRole("button", { name: "Cancelar assinatura" }));
    expect(attempts).toBe(0);
    await user.click(screen.getByRole("button", { name: "Confirmar alteração" }));
    await screen.findByText("Alteração não confirmada");
    await user.click(screen.getByRole("button", { name: "Confirmar alteração" }));
    expect(await screen.findByText("Cancelada")).toBeInTheDocument();
    expect(headers[0].get("idempotency-key")).toBe(headers[1].get("idempotency-key"));
    expect(headers[0].get("x-csrf-token")).toBe("csrf");
    expect(headers[0].get("x-step-up-token")).toBe("fresh-proof");
  });
  it("envia somente o plano alvo e apresenta troca pendente sem liberar recursos", async () => {
    const read = mockRead(); const impl = read.getMockImplementation()!; let body: unknown;
    read.mockImplementation((input, init) => {
      if (init?.method === "POST") { expect(String(input)).toContain("/change-plan"); body = JSON.parse(String(init.body)); return response(200, { ...sub, pending_plan_name: "Plano Pro" }); }
      return impl(input, init);
    });
    const user = userEvent.setup(); render(<BillingPage />);
    await user.click(await screen.findByRole("button", { name: "Mudar para Plano Pro" }));
    await user.click(screen.getByRole("button", { name: "Confirmar alteração" }));
    await screen.findByText("Troca aguardando pagamento"); expect(body).toEqual({ target_plan_id: "test-pro" });
  });
  it("descarta dados e confirmacao ao trocar de tenant", async () => {
    const read = mockRead(); const user = userEvent.setup(); const view = render(<BillingPage />);
    await user.click(await screen.findByRole("button", { name: "Cancelar assinatura" }));
    context.tenant = "b";
    read.mockImplementation((input) => String(input).endsWith("/plans") ? response(200, { items: [] }) : response(404, { code: "NOT_FOUND" }));
    view.rerender(<BillingPage />);
    expect(screen.queryByText("Assinatura atual")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirmar alteração" })).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Nenhuma assinatura configurada")).toBeInTheDocument());
  });
});


describe("Entrada comercial pela Web", () => {
  it("revisa plano e documento antes de iniciar trial; nao emite cobranca", async () => {
    const read = mockRead({ code: "NOT_FOUND" }, 404);
    const impl = read.getMockImplementation()!;
    let submitted: unknown;
    read.mockImplementation((input, init) => {
      if (init?.method === "PUT") {
        submitted = JSON.parse(String(init.body));
        return response(200, { ...sub, status: "TRIAL", trial_ends_at: "2026-10-22T00:00:00Z" });
      }
      return impl(input, init);
    });
    const user = userEvent.setup(); render(<BillingPage />);
    await user.selectOptions(await screen.findByLabelText("Plano"), "test-basic");
    await user.type(screen.getByLabelText("CPF ou CNPJ do titular"), "11144477735");
    await user.click(screen.getByLabelText("Iniciar período de teste de 7 dias"));
    await user.click(screen.getByRole("button", { name: "Revisar contratação" }));
    expect(submitted).toBeUndefined();
    expect(screen.getByText("Período de teste: 7 dias")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirmar contratação" }));
    expect(await screen.findByText("Assinatura atual")).toBeInTheDocument();
    expect(submitted).toEqual({ plan_id: "test-basic", customer_document: "11144477735", start_trial: true, initial_only: true, expected_plan_fingerprint: plan.fingerprint });
    expect(read.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
    expect(screen.queryByLabelText("CPF ou CNPJ do titular")).not.toBeInTheDocument();
  });
  it("entrada sem trial aguarda pagamento e nao libera acesso", async () => {
    const read = mockRead({ code: "NOT_FOUND" }, 404); const impl = read.getMockImplementation()!;
    read.mockImplementation((input, init) => init?.method === "PUT" ? response(200, { ...sub, status: "PENDING_PAYMENT", entitlement_access_active: false }) : impl(input, init));
    const user = userEvent.setup(); render(<BillingPage />);
    await user.selectOptions(await screen.findByLabelText("Plano"), "test-basic");
    await user.type(screen.getByLabelText("CPF ou CNPJ do titular"), "11144477735");
    await user.click(screen.getByRole("button", { name: "Revisar contratação" }));
    await user.click(screen.getByRole("button", { name: "Confirmar contratação" }));
    expect(await screen.findByText("Aguardando pagamento")).toBeInTheDocument();
    expect(screen.getByText("Bloqueado")).toBeInTheDocument();
  });
  it("mantem chave e corpo no retry apos falha e envia CSRF/step-up", async () => {
    const read = mockRead({ code: "NOT_FOUND" }, 404); const impl = read.getMockImplementation()!;
    const writes: RequestInit[] = [];
    read.mockImplementation((input, init) => {
      if (init?.method === "PUT") {
        writes.push(init);
        return writes.length === 1 ? Promise.reject(new TypeError("network")) : response(200, { ...sub, status: "PENDING_PAYMENT" });
      }
      return impl(input, init);
    });
    const user = userEvent.setup(); render(<BillingPage />);
    await user.selectOptions(await screen.findByLabelText("Plano"), "test-basic");
    await user.type(screen.getByLabelText("CPF ou CNPJ do titular"), "11144477735");
    await user.click(screen.getByRole("button", { name: "Revisar contratação" }));
    await user.click(screen.getByRole("button", { name: "Confirmar contratação" }));
    await screen.findByText("Contratação não confirmada");
    await user.click(screen.getByRole("button", { name: "Confirmar contratação" }));
    await screen.findByText("Assinatura atual");
    expect(writes[0].body).toBe(writes[1].body);
    const first = new Headers(writes[0].headers); const second = new Headers(writes[1].headers);
    expect(first.get("idempotency-key")).toBe(second.get("idempotency-key"));
    expect(first.get("x-csrf-token")).toBe("csrf");
    expect(first.get("x-step-up-token")).toBe("fresh-proof");
  });
  it("exige step-up para confirmar e esconde formulario de papel somente de leitura", async () => {
    context.ready = false; mockRead({ code: "NOT_FOUND" }, 404);
    const user = userEvent.setup(); const view = render(<BillingPage />);
    await user.selectOptions(await screen.findByLabelText("Plano"), "test-basic");
    await user.type(screen.getByLabelText("CPF ou CNPJ do titular"), "11144477735");
    await user.click(screen.getByRole("button", { name: "Revisar contratação" }));
    expect(screen.getByRole("button", { name: "Confirmar contratação" })).toBeDisabled();
    context.roles = ["ADMIN"]; context.tenant = "readonly"; view.rerender(<BillingPage />);
    await screen.findByText("Nenhuma assinatura configurada");
    expect(screen.queryByLabelText("CPF ou CNPJ do titular")).not.toBeInTheDocument();
  });
  it("recusa condicoes alteradas sem assumir assinatura criada", async () => {
    const read = mockRead({ code: "NOT_FOUND" }, 404); const impl = read.getMockImplementation()!;
    read.mockImplementation((input, init) => init?.method === "PUT" ? response(409, { code: "BILLING_PLAN_CHANGED", message: "As condições do plano mudaram." }) : impl(input, init));
    const user = userEvent.setup(); render(<BillingPage />);
    await user.selectOptions(await screen.findByLabelText("Plano"), "test-basic");
    await user.type(screen.getByLabelText("CPF ou CNPJ do titular"), "11144477735");
    await user.click(screen.getByRole("button", { name: "Revisar contratação" }));
    await user.click(screen.getByRole("button", { name: "Confirmar contratação" }));
    expect(await screen.findByText("As condições do plano mudaram.")).toBeInTheDocument();
    expect(screen.queryByText("Assinatura atual")).not.toBeInTheDocument();
  });
});
