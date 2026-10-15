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
    if (String(input).endsWith("/billing/subscription")) return response(status, subscription);
    if (String(input).endsWith("/billing/plans")) return response(catalogStatus, { items: [{ ...plan, monthly_price: "99.00" }, { ...plan, plan_id: "test-pro", name: "Plano Pro" }] });
    throw new Error(`Unexpected ${input}`);
  });
}
beforeEach(() => { context.tenant = "a"; context.roles = ["OWNER"]; context.ready = true; setCsrfToken("csrf"); });
afterEach(() => { vi.restoreAllMocks(); setCsrfToken(null); });

describe("Billing Web", () => {
  it("mostra condicoes contratadas distintas do catalogo, limites e consumo indisponivel", async () => {
    const fetch = mockRead(); render(<BillingPage />);
    expect(within(await screen.findByRole("region", { name: "Assinatura atual" })).getByText("R$ 12,50")).toBeInTheDocument();
    expect(screen.getByText("R$ 99,00")).toBeInTheDocument();
    expect(screen.getByText("Medição de consumo ainda indisponível")).toBeInTheDocument();
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
