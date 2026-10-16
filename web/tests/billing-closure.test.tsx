import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BillingClosurePanel } from "@/components/BillingClosurePanel";
import type { BillingClosure } from "@/contracts/types";
import { setCsrfToken } from "@/lib/api/client";

const quote: BillingClosure = { state: "INVOICE_REQUIRED", fingerprint: "a".repeat(64), amount: "5.00", minimum: "5.00",
  lifecycle_id: "fixture-life", cycle_id: "fixture-cycle", invoice: null, provider: "SIMULATOR", mode: "SIMULATOR" };
const response = (value: unknown) => new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
const proof = (ready = true) => ({ ready, testMode: true, headers: vi.fn(() => ({ "x-step-up-token": "proof" })),
  onIdToken: vi.fn(), consumePresentedToken: vi.fn(), noteError: vi.fn(), stepUpMessage: null });
beforeEach(() => setCsrfToken("csrf"));
afterEach(() => { vi.restoreAllMocks(); setCsrfToken(null); });

describe("Final usage closure", () => {
  it("reviews delivered extra without a new monthly fee and treats invoice registration as pending payment", async () => {
    const user = userEvent.setup(); const closed = vi.fn();
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response(quote))
      .mockResolvedValueOnce(response({ ...quote, state: "INVOICED", invoice: "fixture-final" }));
    render(<BillingClosurePanel stepUp={proof()} onClosed={closed} />);
    await user.click(await screen.findByRole("button", { name: "Revisar fechamento final" }));
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Confirmar fechamento final" })).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /Conferi o consumo final/ }));
    await user.click(screen.getByRole("button", { name: "Confirmar fechamento final" }));
    await screen.findByText(/A quitação depende da confirmação do pagamento/);
    expect(closed).toHaveBeenCalledOnce();
    expect(JSON.parse(String(fetch.mock.calls[1][1]?.body))).toEqual({ fingerprint: quote.fingerprint, accept: true });
    expect(new Headers(fetch.mock.calls[1][1]?.headers).get("x-csrf-token")).toBe("csrf");
  });

  it("records absorbed residual without presenting it as a payment", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response({ ...quote, amount: "2.00", state: "ABSORBABLE" }))
      .mockResolvedValueOnce(response({ ...quote, amount: "2.00", state: "ABSORBED" }));
    render(<BillingClosurePanel stepUp={proof()} onClosed={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: "Revisar fechamento final" }));
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Confirmar fechamento final" }));
    await screen.findByText(/Nenhum pagamento foi registrado por essa absorção/);
    expect(screen.queryByText(/Fatura final registrada/)).not.toBeInTheDocument();
  });

  it("reuses the exact confirmation after uncertainty and requires recent authentication", async () => {
    const user = userEvent.setup();
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response(quote))
      .mockRejectedValueOnce(new TypeError("lost response")).mockResolvedValueOnce(response({ ...quote, state: "INVOICED" }));
    const view = render(<BillingClosurePanel stepUp={proof()} onClosed={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: "Revisar fechamento final" }));
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Confirmar fechamento final" }));
    await screen.findByText(/Fechamento ainda não confirmado/);
    await user.click(screen.getByRole("button", { name: "Confirmar fechamento final" }));
    await screen.findByText(/A quitação depende da confirmação/);
    expect(fetch.mock.calls[1][1]?.body).toBe(fetch.mock.calls[2][1]?.body);
    expect(new Headers(fetch.mock.calls[1][1]?.headers).get("idempotency-key")).toBe(new Headers(fetch.mock.calls[2][1]?.headers).get("idempotency-key"));
    view.unmount(); fetch.mockResolvedValue(response(quote));
    render(<BillingClosurePanel stepUp={proof(false)} onClosed={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: "Revisar fechamento final" }));
    await user.click(screen.getByRole("checkbox"));
    expect(screen.getByRole("button", { name: "Confirmar fechamento final" })).toBeDisabled();
  });

  it("offers no new invoice while a reservation or another financial obligation needs reconciliation", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ ...quote, state: "PENDING_USAGE" }));
    const view = render(<BillingClosurePanel stepUp={proof()} onClosed={vi.fn()} />);
    await screen.findByText(/Há gerações pendentes/);
    expect(screen.queryByRole("button", { name: "Revisar fechamento final" })).not.toBeInTheDocument();
    view.unmount(); fetch.mockResolvedValue(response({ ...quote, state: "RECONCILIATION_REQUIRED" }));
    render(<BillingClosurePanel stepUp={proof()} onClosed={vi.fn()} />);
    await screen.findByText(/Este consumo já está vinculado/);
    expect(screen.queryByRole("button", { name: "Revisar fechamento final" })).not.toBeInTheDocument();
  });
});

it("preserva consumo encerrado pela garantia sem oferecer outra fatura", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ ...quote, state: "GUARANTEE_CLOSED" }));
  render(<BillingClosurePanel stepUp={proof()} onClosed={vi.fn()} />);
  await screen.findByText(/este excedente não será cobrado novamente/);
  expect(screen.queryByRole("button", { name: "Revisar fechamento final" })).not.toBeInTheDocument();
});
