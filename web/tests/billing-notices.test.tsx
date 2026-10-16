import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { BillingNoticesPanel } from "@/components/BillingNoticesPanel";
import type { BillingNotice } from "@/contracts/types";
import { setCsrfToken } from "@/lib/api/client";

const notice: BillingNotice = { id: "fixture-notice", billing_id: "fixture-bill", gateway_charge_id: "fixture-gateway",
  channel: "IN_APP", offset_days: 3, scheduled_at: "2026-10-16T03:00:00Z", created_at: "2026-10-17T03:00:00Z",
  due_at: "2026-10-13T03:00:00Z", amount: "149.00", currency: "BRL", mode: "SIMULATOR",
  invoice_state: "PENDING_CONFIRMATION", read_at: null };
const response = (value: unknown) => new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
beforeEach(() => setCsrfToken("fixture-csrf"));
afterEach(() => { vi.restoreAllMocks(); setCsrfToken(null); });

it("distinguishes inbox availability, reading, payment and external message delivery", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ items: [notice], next_cursor: null }));
  render(<BillingNoticesPanel />);
  await screen.findByRole("region", { name: "Aviso de cobrança D3" });
  expect(screen.getByText(/não confirma envio de e-mail ou SMS, leitura ou pagamento/)).toBeInTheDocument();
  expect(screen.getByText(/Se você já pagou, use Conferir pagamento/)).toBeInTheDocument();
  expect(screen.getByText(/Marco previsto:.*Disponível no aplicativo em/)).toBeInTheDocument();
  expect(screen.getByText(/Aviso de simulação/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Marcar como lido" })).toBeEnabled();
});

it("retries individual reading with the same key and CSRF without claiming payment", async () => {
  const user = userEvent.setup();
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response({ items: [notice], next_cursor: null }))
    .mockRejectedValueOnce(new TypeError("lost response"))
    .mockResolvedValueOnce(response({ id: notice.id, read_at: "2026-10-18T03:00:00Z" }));
  render(<BillingNoticesPanel />);
  await user.click(await screen.findByRole("button", { name: "Marcar como lido" }));
  await screen.findByText(/Leitura ainda não confirmada/);
  await user.click(screen.getByRole("button", { name: "Marcar como lido" }));
  await screen.findByText(/Lido por você/);
  expect(new Headers(fetch.mock.calls[1][1]?.headers).get("idempotency-key")).toBe(new Headers(fetch.mock.calls[2][1]?.headers).get("idempotency-key"));
  expect(new Headers(fetch.mock.calls[1][1]?.headers).get("x-csrf-token")).toBe("fixture-csrf");
  expect(fetch.mock.calls[1][1]?.body).toBeUndefined();
  expect(screen.getByText(/confirmação do pagamento ainda não foi registrada/)).toBeInTheDocument();
});

it("loads another page and keeps corrected invoices as history without a new demand", async () => {
  const user = userEvent.setup();
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response({ items: [notice], next_cursor: notice.id }))
    .mockResolvedValueOnce(response({ items: [{ ...notice, id: "fixture-older", offset_days: 0, invoice_state: "PAYMENT_CONFIRMED" }], next_cursor: null }));
  render(<BillingNoticesPanel />);
  await user.click(await screen.findByRole("button", { name: "Carregar mais avisos" }));
  const history = await screen.findByRole("region", { name: "Aviso de cobrança D0" });
  expect(within(history).getByText(/pagamento foi confirmado/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Carregar mais avisos" })).not.toBeInTheDocument();
});

it("does not show a payment demand for a receipt conflict", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ items: [{ ...notice, invoice_state: "REVIEW_REQUIRED" }], next_cursor: null }));
  render(<BillingNoticesPanel />);
  await screen.findByText(/Este aviso não confirma uma dívida adicional/);
  expect(screen.queryByText(/Se você já pagou/)).not.toBeInTheDocument();
});
