import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BillingChargeHistoryPanel } from "@/components/BillingChargeHistoryPanel";
import type { BillingChargeHistoryItem } from "@/contracts/types";

const item: BillingChargeHistoryItem = {
  billing_id: "bill-one", gateway_charge_id: "pay-one", competence: "2026-10", currency: "BRL",
  amount: "20.50", plan_id: "basic", purpose: "REGULAR", created_at: "2026-10-15T13:00:00Z",
  gateway_status: "PENDING", gateway_provider: "ASAAS", gateway_mode: "SANDBOX",
  status_observed_at: "2026-10-15T13:00:00Z", status_source: "CREATE",
  invoice_url: "https://sandbox.asaas.com/i/test-one",
};
const json = (status: number, body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }));
afterEach(() => vi.restoreAllMocks());

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
