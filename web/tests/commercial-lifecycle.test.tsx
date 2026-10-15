import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CommercialLifecycleActions } from "@/components/CommercialLifecycleActions";
import type { BillingPlan, BillingSubscription } from "@/contracts/types";
import { setCsrfToken } from "@/lib/api/client";

const plan: BillingPlan = {
  fingerprint: "a".repeat(64), plan_id: "a", name: "Teste A", currency: "BRL",
  monthly_price: "1.00", included_credits: "10", extra_credit_unit_price: "1.00", trial_days: 7,
  cancellation_mode: "PERIOD_END", reactivation_mode: "PAYMENT_REQUIRED",
  reactivation_billing_mode: "CURRENT_PLAN_FULL_CYCLE",
  plan_changes: [{ target_plan_id: "b", kind: "UPGRADE", activation: "NEXT_ANNIVERSARY", billing_mode: "TARGET_PLAN_FULL_CYCLE" }],
};
const target: BillingPlan = { ...plan, fingerprint: "b".repeat(64), plan_id: "b", name: "Teste B", monthly_price: "2.00", plan_changes: [] };
const sub: BillingSubscription = { tenant_id: "a", customer_ref: "a", customer_document: "fixture",
  plan_id: "a", plan_name: "Teste A", status: "ACTIVE", commercial_terms: plan,
  entitlement_access_active: true, paid_period_ends_at: "2026-11-15T12:00:00Z",
  entitlements: { max_users: 2, max_active_campaigns: 3, channels: [], ai_capabilities: [], resources: [] } };
const response = () => new Response(JSON.stringify(sub), { status: 200, headers: { "Content-Type": "application/json" } });
function proof(ready = true) { return { ready, testMode: true, headers: vi.fn(() => ({ "x-step-up-token": "proof" })),
  onIdToken: vi.fn(), consumePresentedToken: vi.fn(), noteError: vi.fn(), stepUpMessage: null }; }
beforeEach(() => setCsrfToken("csrf"));
afterEach(() => { vi.restoreAllMocks(); setCsrfToken(null); });

describe("Commercial lifecycle", () => {
  it("reviews future terms and sends the target fingerprint only after confirmation", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(response());
    const updated = vi.fn(); const user = userEvent.setup();
    render(<CommercialLifecycleActions subscription={sub} plans={[plan, target]} stepUp={proof()} onUpdated={updated} />);
    await user.click(screen.getByRole("button", { name: "Agendar Teste B" }));
    expect(screen.getByText(/sem cobrança proporcional/)).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Confirmar solicitação" }));
    await screen.findByRole("status");
    expect(fetch.mock.calls[0][0]).toContain("/change-plan");
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({ target_plan_id: "b", expected_plan_fingerprint: target.fingerprint });
    expect(updated).toHaveBeenCalledOnce();
  });

  it("keeps period-end cancellation distinct from explicit immediate closure", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async () => response());
    const user = userEvent.setup();
    render(<CommercialLifecycleActions subscription={sub} plans={[]} stepUp={proof()} onUpdated={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Cancelar renovação" }));
    await user.click(screen.getByRole("button", { name: "Confirmar solicitação" }));
    await screen.findByRole("status");
    expect(fetch.mock.calls[0][1]?.body).toBeUndefined();
    await user.click(screen.getByRole("button", { name: "Encerrar imediatamente" }));
    await user.click(screen.getByRole("button", { name: "Confirmar solicitação" }));
    await screen.findByRole("status");
    expect(JSON.parse(String(fetch.mock.calls[1][1]?.body))).toEqual({ immediate: true });
  });

  it("reuses the exact request after uncertain completion", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new TypeError("offline")).mockResolvedValueOnce(response());
    const user = userEvent.setup();
    render(<CommercialLifecycleActions subscription={{ ...sub, cancel_at_period_end: sub.paid_period_ends_at }} plans={[]} stepUp={proof()} onUpdated={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Manter assinatura" }));
    await user.click(screen.getByRole("button", { name: "Confirmar solicitação" }));
    await screen.findByText(/Resultado não confirmado/);
    await user.click(screen.getByRole("button", { name: "Confirmar solicitação" }));
    await screen.findByRole("status");
    expect(fetch.mock.calls[0][0]).toContain("/reactivate");
    expect(fetch.mock.calls[0][1]?.body).toBe(fetch.mock.calls[1][1]?.body);
    const headers = new Headers(fetch.mock.calls[0][1]?.headers);
    expect(headers.get("idempotency-key")).toBe(new Headers(fetch.mock.calls[1][1]?.headers).get("idempotency-key"));
    expect(headers.get("x-csrf-token")).toBe("csrf");
  });

  it("requires recent authentication and labels a closed subscription as a new paid contract", async () => {
    const fetch = vi.spyOn(globalThis, "fetch"); const user = userEvent.setup();
    render(<CommercialLifecycleActions subscription={{ ...sub, status: "CANCELED" }} plans={[]} stepUp={proof(false)} onUpdated={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Solicitar reativação" }));
    expect(screen.getByText(/sem novo trial/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirmar solicitação" })).toBeDisabled();
    expect(fetch).not.toHaveBeenCalled();
  });
});
