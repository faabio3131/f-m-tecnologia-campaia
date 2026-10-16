import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BillingGuaranteePanel } from "@/components/BillingGuaranteePanel";
import type { BillingGuarantee } from "@/contracts/types";
import { setCsrfToken } from "@/lib/api/client";

const quote: BillingGuarantee = { state: "ELIGIBLE", fingerprint: "b".repeat(64), first_paid_at: "2026-10-16T01:00:00Z",
  deadline: "2026-10-23T01:00:00Z", paid_amount: "12.50", currency: "BRL", request_id: null, requested_at: null,
  items: [{ billing_id: "bill-fixture", gateway_charge_id: "sim-fixture", amount: "12.50", paid_at: "2026-10-16T01:00:00Z",
    purpose: "REGULAR", provider: "SIMULATOR", mode: "SIMULATOR" }] };
const response = (value: unknown) => new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
const proof = (ready = true) => ({ ready, testMode: true, headers: vi.fn(() => ({ "x-step-up-token": "fixture-proof" })),
  onIdToken: vi.fn(), consumePresentedToken: vi.fn(), noteError: vi.fn(), stepUpMessage: null });
const requested = { ...quote, state: "REQUESTED", request_id: "fixture-case", requested_at: "2026-10-16T02:00:00Z" };
beforeEach(() => setCsrfToken("fixture-csrf"));
afterEach(() => { vi.restoreAllMocks(); setCsrfToken(null); });

describe("First paid guarantee", () => {
  it("requires review, explicit immediate paid end and recent authentication before recording a request", async () => {
    const user = userEvent.setup(); const onRequested = vi.fn(); const stepUp = proof(false);
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response(quote)).mockResolvedValueOnce(response(requested));
    const view = render(<BillingGuaranteePanel stepUp={stepUp} onRequested={onRequested} />);
    await user.click(await screen.findByRole("button", { name: "Revisar solicitação de garantia" }));
    expect(fetch).toHaveBeenCalledTimes(1);
    const confirm = screen.getByRole("button", { name: "Confirmar solicitação de garantia" });
    expect(confirm).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /acesso pago será encerrado imediatamente/ }));
    expect(confirm).toBeDisabled();
    view.rerender(<BillingGuaranteePanel stepUp={{ ...stepUp, ready: true }} onRequested={onRequested} />);
    await user.click(confirm);
    await screen.findByText(/recebimento do pedido não confirma o estorno/);
    expect(onRequested).toHaveBeenCalledOnce();
    expect(JSON.parse(String(fetch.mock.calls[1][1]?.body))).toEqual({ fingerprint: quote.fingerprint, accept: true });
    expect(new Headers(fetch.mock.calls[1][1]?.headers).get("x-csrf-token")).toBe("fixture-csrf");
    expect(stepUp.consumePresentedToken).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Revisar solicitação de garantia" })).not.toBeInTheDocument();
  });

  it("retains the same request after uncertainty and never presents registration as money returned", async () => {
    const user = userEvent.setup();
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response(quote))
      .mockRejectedValueOnce(new TypeError("lost response")).mockResolvedValueOnce(response(requested));
    render(<BillingGuaranteePanel stepUp={proof()} onRequested={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: "Revisar solicitação de garantia" }));
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Confirmar solicitação de garantia" }));
    await screen.findByText(/Pedido ainda não confirmado/);
    await user.click(screen.getByRole("button", { name: "Confirmar solicitação de garantia" }));
    await screen.findByText(/recebimento do pedido não confirma o estorno/);
    expect(fetch.mock.calls[1][1]?.body).toBe(fetch.mock.calls[2][1]?.body);
    expect(new Headers(fetch.mock.calls[1][1]?.headers).get("idempotency-key")).toBe(new Headers(fetch.mock.calls[2][1]?.headers).get("idempotency-key"));
    expect(screen.getByText(/disponibilização da devolução depende do meio de pagamento/)).toBeInTheDocument();
  });

  it("preserves rights after the commercial window without enabling an unsupported automatic request", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ ...quote, state: "EXPIRED" }));
    render(<BillingGuaranteePanel stepUp={proof()} onRequested={vi.fn()} />);
    await screen.findByText(/Direitos legais e revisão de cobranças indevidas permanecem preservados/);
    expect(screen.queryByRole("button", { name: "Revisar solicitação de garantia" })).not.toBeInTheDocument();
  });
});

it("separa tratamento iniciado, pendencia no provedor e devolucao concluida com ajuste ainda pendente", async () => {
  const user = userEvent.setup();
  const progress = { ...quote, state: "PROCESSING", request_id: "fixture-case", requested_at: "2026-10-16T02:00:00Z",
    processing_started_at: "2026-10-16T03:00:00Z", refund_progress: [
      { billing_id: "bill-fixture", gateway_charge_id: "sim-fixture", paid_amount: "12.50", completed_amount: "0.00", state: "PROVIDER_PENDING", mode: "SIMULATOR" }] };
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response(progress))
    .mockResolvedValueOnce(response({ ...progress, refund_progress: [{ ...progress.refund_progress[0],
      completed_amount: "12.50", state: "REFUND_DONE_ADJUSTMENT_PENDING" }] }));
  render(<BillingGuaranteePanel stepUp={proof()} onRequested={vi.fn()} />);
  await screen.findByText("Devolução em processamento no provedor.");
  expect(screen.queryByText(/Devolução integral informada pelo provedor; ajuste contratual pendente/)).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Atualizar garantia" }));
  await screen.findByText("Devolução integral informada pelo provedor; ajuste contratual pendente.");
  expect(screen.getByText("Tratamento iniciado. Devoluções e ajustes são conferidos separadamente.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Confirmar solicitação de garantia" })).not.toBeInTheDocument();
  expect(fetch.mock.calls.every(([, init]) => init?.method === "GET")).toBe(true);
});
