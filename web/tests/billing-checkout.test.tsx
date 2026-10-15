import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BillingCheckoutPanel } from "@/components/BillingCheckoutPanel";
import type { BillingCheckout } from "@/contracts/types";
import { setCsrfToken } from "@/lib/api/client";

const checkout: BillingCheckout = { state: "READY", available_at: null, invoice_url: null, quote: {
  organization_name: "Organização de teste", holder_document_masked: "***7735", fingerprint: "a".repeat(64),
  billing_id: "fixture-obligation", competence: "cycle:0", amount: "12.50", currency: "BRL",
  plan_id: "fixture-plan", plan_name: "Plano de teste", included_credits: 10, extra_credit_price: "1.00",
  action_weights: [{ action: "strategy", credits: 5 }], policy_version: "fixture-v1", purpose: "REGULAR",
  cycle_index: 0, due_at: "2026-10-15T03:00:00Z", period_starts_at: null, period_ends_at: null,
  lines: [{ description: "Mensalidade antecipada", amount: "12.50" }], provider: "ASAAS", mode: "SANDBOX",
} };
const registered = { ...checkout, state: "REGISTERED", invoice_url: "https://sandbox.asaas.com/i/fixture-invoice" };
const response = (value: unknown) => new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
const proof = (ready = true) => ({ ready, testMode: true, headers: vi.fn(() => ({ "x-step-up-token": "proof" })),
  onIdToken: vi.fn(), consumePresentedToken: vi.fn(), noteError: vi.fn(), stepUpMessage: null });
beforeEach(() => setCsrfToken("csrf-test"));
afterEach(() => { vi.restoreAllMocks(); setCsrfToken(null); });

describe("Reviewed billing checkout", () => {
  it("requires explicit review and acceptance and never treats invoice registration as payment", async () => {
    const user = userEvent.setup(); const issued = vi.fn();
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response(checkout))
      .mockResolvedValueOnce(response({ gateway_charge_id: "fixture-payment" })).mockResolvedValueOnce(response(registered));
    render(<BillingCheckoutPanel stepUp={proof()} onIssued={issued} />);
    await screen.findByRole("region", { name: "Valores da cobrança" });
    expect(screen.getByText(/Organização de teste/)).toBeInTheDocument();
    expect(screen.getByText(/primeiro ciclo começa na confirmação/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Revisar e emitir cobrança" }));
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Confirmar cobrança" })).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /Conferi o plano/ }));
    await user.click(screen.getByRole("button", { name: "Confirmar cobrança" }));
    expect(await screen.findByRole("status")).toHaveTextContent("O acesso muda somente após confirmação do pagamento");
    expect(await screen.findByRole("link", { name: "Abrir fatura Asaas" })).toHaveAttribute("href", registered.invoice_url);
    expect(issued).toHaveBeenCalledOnce();
    expect(JSON.parse(String(fetch.mock.calls[1][1]?.body))).toEqual({ competence: "cycle:0", expected_quote_fingerprint: checkout.quote!.fingerprint, accept_quote: true });
    expect(new Headers(fetch.mock.calls[1][1]?.headers).get("x-csrf-token")).toBe("csrf-test");
  });

  it("keeps body and key stable when the emission result is uncertain", async () => {
    const user = userEvent.setup();
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response(checkout))
      .mockRejectedValueOnce(new TypeError("lost response")).mockResolvedValueOnce(response({}))
      .mockResolvedValueOnce(response(registered));
    render(<BillingCheckoutPanel stepUp={proof()} onIssued={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: "Revisar e emitir cobrança" }));
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Confirmar cobrança" }));
    await screen.findByText(/Emissão ainda não confirmada/);
    await user.click(screen.getByRole("button", { name: "Confirmar cobrança" }));
    await screen.findByRole("status");
    const first = fetch.mock.calls[1][1]!; const retry = fetch.mock.calls[2][1]!;
    expect(first.body).toBe(retry.body);
    expect(new Headers(first.headers).get("idempotency-key")).toBe(new Headers(retry.headers).get("idempotency-key"));
  });

  it("does not offer premature renewal and preserves explicit closed state", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ ...checkout, state: "NOT_DUE", quote: null, available_at: "2026-11-15T12:00:00Z" }));
    const view = render(<BillingCheckoutPanel stepUp={proof()} onIssued={vi.fn()} />);
    await screen.findByText(/Nenhuma nova mensalidade será emitida antes/);
    expect(screen.queryByRole("button", { name: "Revisar e emitir cobrança" })).not.toBeInTheDocument();
    view.unmount();
    vi.mocked(globalThis.fetch).mockResolvedValue(response({ ...checkout, state: "CLOSED", quote: null }));
    render(<BillingCheckoutPanel stepUp={proof()} onIssued={vi.fn()} />);
    await screen.findByText(/A renovação está cancelada/);
  });

  it("requires recent authentication and labels simulation without offering an unsafe invoice URL", async () => {
    const user = userEvent.setup(); const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(checkout));
    const view = render(<BillingCheckoutPanel stepUp={proof(false)} onIssued={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: "Revisar e emitir cobrança" }));
    await user.click(screen.getByRole("checkbox"));
    expect(screen.getByRole("button", { name: "Confirmar cobrança" })).toBeDisabled();
    expect(fetch).toHaveBeenCalledTimes(1);
    view.unmount();
    fetch.mockResolvedValue(response({ ...registered, invoice_url: "https://attacker.example/i/fixture", quote: { ...checkout.quote, provider: "SIMULATOR", mode: "SIMULATOR" } }));
    render(<BillingCheckoutPanel stepUp={proof()} onIssued={vi.fn()} />);
    await screen.findByText(/Simulação: esta cobrança não movimenta dinheiro/);
    expect(screen.queryByRole("link", { name: "Abrir fatura Asaas" })).not.toBeInTheDocument();
  });
});
