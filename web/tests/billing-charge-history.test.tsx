import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BillingChargeHistoryPanel } from "@/components/BillingChargeHistoryPanel";
import { setCsrfToken } from "@/lib/api/client";
import type { BillingChargeHistoryItem } from "@/contracts/types";

const item: BillingChargeHistoryItem = {
  billing_id: "bill-one", gateway_charge_id: "pay-one", competence: "2026-10", currency: "BRL",
  amount: "20.50", plan_id: "basic", purpose: "REGULAR", created_at: "2026-10-15T13:00:00Z",
  gateway_status: "PENDING", gateway_provider: "ASAAS", gateway_mode: "SANDBOX",
  status_observed_at: "2026-10-15T13:00:00Z", status_source: "CREATE",
  invoice_url: "https://sandbox.asaas.com/i/test-one",
};
const json = (status: number, body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }));
beforeEach(() => setCsrfToken("fixture-csrf"));
afterEach(() => { vi.restoreAllMocks(); setCsrfToken(null); });

describe("Billing charge history", () => {
  it("renderiza historico, ambiente e link do provedor sem emitir cobranca", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(() => json(200, { items: [item], next_cursor: null }));
    render(<BillingChargeHistoryPanel />);
    expect(await screen.findByText("R$ 20,50")).toBeInTheDocument();
    expect(screen.getByText("Sandbox (teste)")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Abrir fatura no Asaas — teste" });
    expect(link).toHaveAttribute("href", item.invoice_url);
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link).toHaveAttribute("referrerpolicy", "no-referrer");
    expect(fetch.mock.calls.every(([, init]) => init?.method === "GET")).toBe(true);
  });
  it("registros legados nao inventam status, ambiente nem link", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => json(200, { items: [{ ...item, gateway_status: null, gateway_mode: null, status_source: null, status_observed_at: null, invoice_url: null }], next_cursor: null }));
    render(<BillingChargeHistoryPanel />);
    expect(await screen.findByText("Sem observação registrada")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.queryByText("Pendente")).not.toBeInTheDocument();
  });
  it("bloqueia navegacao para host incorreto ou outro ambiente", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => json(200, { items: [
      { ...item, invoice_url: "https://evil.test/i/test" },
      { ...item, gateway_charge_id: "pay-two", invoice_url: "https://www.asaas.com/i/test" },
      { ...item, gateway_charge_id: "pay-three", gateway_mode: "SIMULATOR" },
    ], next_cursor: null }));
    render(<BillingChargeHistoryPanel />);
    await screen.findByText("Simulação");
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
  it("mostra vazio e trata negacao sem expor dados internos", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(() => json(403, { code: "PERMISSION_DENIED", message: "private/path" }));
    const user = userEvent.setup(); render(<BillingChargeHistoryPanel />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível consultar");
    expect(screen.queryByText("private/path")).not.toBeInTheDocument();
    fetch.mockImplementation(() => json(200, { items: [], next_cursor: null }));
    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(await screen.findByText("Nenhuma cobrança registrada")).toBeInTheDocument();
  });
  it("pagina e tenta novamente com o mesmo cursor preservando os dados existentes", async () => {
    let attempts = 0; const paths: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      paths.push(String(input));
      if (!String(input).includes("cursor=")) return json(200, { items: [item], next_cursor: "pay-one" });
      if (++attempts === 1) return Promise.reject(new TypeError("network"));
      return json(200, { items: [{ ...item, billing_id: "bill-two", gateway_charge_id: "pay-two", status_source: "WEBHOOK", gateway_status: "CONFIRMED" }], next_cursor: null });
    });
    const user = userEvent.setup(); render(<BillingChargeHistoryPanel />);
    await user.click(await screen.findByRole("button", { name: "Carregar mais cobranças" }));
    await screen.findByRole("alert");
    expect(screen.getByText("bill-one")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(await screen.findByText("bill-two")).toBeInTheDocument();
    expect(within(screen.getByRole("article", { name: "Cobrança bill-two" })).getByText("Confirmada")).toBeInTheDocument();
    expect(paths[1]).toBe(paths[2]);
    expect(screen.queryByRole("button", { name: "Carregar mais cobranças" })).not.toBeInTheDocument();
  });
});

const stepUp = (ready = true) => ({ ready, testMode: false, headers: () => ({ "x-step-up-token": "fixture-proof" }),
  consumePresentedToken: vi.fn(), noteError: vi.fn(), onIdToken: vi.fn(), stepUpMessage: null });

it("mostra divergencia e valor zero sem declarar quitacao ou inventar valor ausente", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(() => json(200, { items: [
    { ...item, gateway_status: "CONFIRMED", payment_reconciliation_state: "AMOUNT_MISMATCH", gateway_observed_amount: "0", status_source: "RECONCILIATION" },
    { ...item, billing_id: "bill-missing", gateway_charge_id: "pay-missing", payment_reconciliation_state: "AMOUNT_MISSING", gateway_observed_amount: null },
  ], next_cursor: null }));
  render(<BillingChargeHistoryPanel />);
  expect(await screen.findByText("R$ 0,00")).toBeInTheDocument();
  expect(screen.getByText("Não informado")).toBeInTheDocument();
  expect(screen.getByText("Consulta ao provedor")).toBeInTheDocument();
  expect(screen.queryByText("Confirmada")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Conferir recebimento no provedor" })).not.toBeInTheDocument();
});

it("exige autenticacao recente e preserva a chave apos consulta incerta sem enviar valor ou emitir fatura", async () => {
  const proof = stepUp(false); const onReconciled = vi.fn(); const requests: RequestInit[] = [];
  let attempts = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
    if (init?.method === "POST") {
      requests.push(init);
      if (++attempts === 1) return Promise.reject(new TypeError("network"));
      return json(200, { accepted: true, reconciled: false });
    }
    return json(200, { items: [{ ...item, reconciliation_available: true }], next_cursor: null });
  });
  const user = userEvent.setup();
  const view = render(<BillingChargeHistoryPanel canManage stepUp={proof} onReconciled={onReconciled} />);
  expect(await screen.findByRole("button", { name: "Conferir recebimento no provedor" })).toBeDisabled();
  view.rerender(<BillingChargeHistoryPanel canManage stepUp={{ ...proof, ready: true }} onReconciled={onReconciled} />);
  await user.click(screen.getByRole("button", { name: "Conferir recebimento no provedor" }));
  await screen.findByText(/Não foi possível confirmar a consulta/);
  await user.click(screen.getByRole("button", { name: "Conferir recebimento no provedor" }));
  await screen.findByText(/Consulta registrada/);
  expect(requests).toHaveLength(2);
  expect(requests[0].body).toBeUndefined();
  expect(new Headers(requests[0].headers).get("Idempotency-Key")).toBe(new Headers(requests[1].headers).get("Idempotency-Key"));
  expect(onReconciled).toHaveBeenCalledOnce();
  expect(proof.consumePresentedToken).toHaveBeenCalledOnce();
  expect(screen.queryByText("Confirmada")).not.toBeInTheDocument();
});

it("revisa retirada de fatura aberta e conserva confirmacao apos incerteza sem afirmar reembolso", async () => {
  const proof = stepUp(); const observed = vi.fn(); let withdrawn = false; const posts: RequestInit[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
    if (init?.method === "POST") {
      posts.push(init);
      if (posts.length === 1) return Promise.reject(new TypeError("unknown"));
      withdrawn = true; return json(200, { state: "VOID" });
    }
    return json(200, { items: [{ ...item, withdrawal_state: withdrawn ? "VOID" : null,
      withdrawal_fingerprint: withdrawn ? null : "a".repeat(64) }], next_cursor: null });
  });
  const user = userEvent.setup();
  render(<BillingChargeHistoryPanel canManage stepUp={proof} onReconciled={observed} />);
  await user.click(await screen.findByRole("button", { name: "Revisar retirada da fatura aberta" }));
  expect(posts).toHaveLength(0);
  expect(screen.getByRole("button", { name: "Confirmar retirada da fatura aberta" })).toBeDisabled();
  await user.click(screen.getByRole("checkbox", { name: /Conferi a fatura/ }));
  await user.click(screen.getByRole("button", { name: "Confirmar retirada da fatura aberta" }));
  await screen.findByText(/Retirada não confirmada/);
  await user.click(screen.getByRole("button", { name: "Confirmar retirada da fatura aberta" }));
  await screen.findByText("Retirada confirmada — sem quitação");
  expect(screen.getByText(/Nenhum pagamento ou reembolso foi registrado/)).toBeInTheDocument();
  expect(posts[0].body).toBe(posts[1].body);
  expect(new Headers(posts[0].headers).get("Idempotency-Key")).toBe(new Headers(posts[1].headers).get("Idempotency-Key"));
  expect(observed).toHaveBeenCalledOnce();
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});

it("separa devolucao em processamento de valor concluido sem liberar outra franquia", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(() => json(200, { items: [
    { ...item, gateway_charge_id: "pay-pending-refund", billing_id: "bill-pending-refund",
      payment_reconciliation_state: "REVERSAL_PENDING", gateway_refund_state: "PROCESSING", gateway_refund_amount: "0.00" },
    { ...item, gateway_charge_id: "pay-done-refund", billing_id: "bill-done-refund",
      payment_reconciliation_state: "REVERSAL_PENDING", gateway_refund_state: "FULL_DONE", gateway_refund_amount: "20.50" },
  ], next_cursor: null }));
  render(<BillingChargeHistoryPanel />);
  expect(await screen.findByText("Há devolução em processamento")).toBeInTheDocument();
  const pending = screen.getByRole("article", { name: "Cobrança bill-pending-refund" });
  expect(within(pending).getByText("R$ 0,00")).toBeInTheDocument();
  expect(within(pending).queryByText("Devolução integral informada pelo provedor")).not.toBeInTheDocument();
  expect(screen.getByText("Devolução integral informada pelo provedor")).toBeInTheDocument();
  expect(screen.getAllByText(/ajuste da assinatura e das obrigações continua em conferência/)).toHaveLength(2);
  expect(screen.queryByText("Confirmada")).not.toBeInTheDocument();
});
