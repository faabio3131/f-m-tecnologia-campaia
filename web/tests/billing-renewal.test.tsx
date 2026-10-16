import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { BillingRenewalPanel } from "@/components/BillingRenewalPanel";
import type { BillingRenewal } from "@/contracts/types";
import { setCsrfToken } from "@/lib/api/client";

const quote: BillingRenewal = { enabled: false, valid: false, can_enable: true, fingerprint: "a".repeat(64),
  lifecycle_id: "fixture-life", plan_name: "Plano", monthly_price: "149.00", currency: "BRL",
  provider: "SIMULATOR", mode: "SIMULATOR", next_due_at: "2026-11-16T03:00:00Z", accepted_at: null };
const response = (value: unknown) => new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
const proof = (ready = true) => ({ ready, testMode: true, headers: vi.fn(() => ({ "x-step-up-token": "fixture-proof" })),
  onIdToken: vi.fn(), consumePresentedToken: vi.fn(), noteError: vi.fn(), stepUpMessage: null });
beforeEach(() => setCsrfToken("fixture-csrf"));
afterEach(() => { vi.restoreAllMocks(); setCsrfToken(null); });

it("requires explicit review and recent authentication to authorize future invoices without claiming automatic debit", async () => {
  const user = userEvent.setup(); const stepUp = proof(false);
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response(quote))
    .mockResolvedValueOnce(response({ ...quote, enabled: true, valid: true }));
  const view = render(<BillingRenewalPanel stepUp={stepUp} />);
  await user.click(await screen.findByRole("button", { name: "Revisar autorização de emissão" }));
  expect(fetch).toHaveBeenCalledOnce();
  expect(screen.getByText(/não autoriza débito automático/)).toBeInTheDocument();
  await user.click(screen.getByRole("checkbox", { name: /Autorizo a emissão das próximas faturas/ }));
  expect(screen.getByRole("button", { name: "Confirmar alteração da emissão" })).toBeDisabled();
  view.rerender(<BillingRenewalPanel stepUp={{ ...stepUp, ready: true }} />);
  await user.click(screen.getByRole("button", { name: "Confirmar alteração da emissão" }));
  await screen.findByText(/Emissão recorrente autorizada para estas condições/);
  expect(fetch.mock.calls[1][1]?.method).toBe("PUT");
  expect(JSON.parse(String(fetch.mock.calls[1][1]?.body))).toEqual({ enabled: true, fingerprint: quote.fingerprint });
  expect(new Headers(fetch.mock.calls[1][1]?.headers).get("x-csrf-token")).toBe("fixture-csrf");
  expect(stepUp.consumePresentedToken).toHaveBeenCalledOnce();
});

it("retains the same disable request after uncertainty and explains that prior invoices are not automatically voided", async () => {
  const user = userEvent.setup();
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response({ ...quote, enabled: true, valid: true }))
    .mockRejectedValueOnce(new TypeError("lost response")).mockResolvedValueOnce(response(quote));
  render(<BillingRenewalPanel stepUp={proof()} />);
  await user.click(await screen.findByRole("button", { name: "Desativar emissão recorrente" }));
  expect(screen.getByText(/não é cancelada automaticamente/)).toBeInTheDocument();
  await user.click(screen.getByRole("checkbox", { name: /Confirmo a desativação/ }));
  await user.click(screen.getByRole("button", { name: "Confirmar alteração da emissão" }));
  await screen.findByText(/Alteração ainda não confirmada/);
  await user.click(screen.getByRole("button", { name: "Confirmar alteração da emissão" }));
  await screen.findByText("Emissão recorrente não autorizada.");
  expect(fetch.mock.calls[1][1]?.body).toBe(fetch.mock.calls[2][1]?.body);
  expect(new Headers(fetch.mock.calls[1][1]?.headers).get("idempotency-key")).toBe(new Headers(fetch.mock.calls[2][1]?.headers).get("idempotency-key"));
});

it("requires a new review after changed terms and never enables auto-conversion during trial", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ ...quote, enabled: true, valid: false }));
  const view = render(<BillingRenewalPanel stepUp={proof()} />);
  await screen.findByText(/precisa de nova revisão/);
  expect(screen.getByRole("button", { name: "Revisar autorização de emissão" })).toBeEnabled();
  view.unmount(); fetch.mockResolvedValue(response({ ...quote, can_enable: false }));
  render(<BillingRenewalPanel stepUp={proof()} />);
  await screen.findByText(/trial não é convertido automaticamente/);
  expect(screen.queryByRole("button", { name: "Revisar autorização de emissão" })).not.toBeInTheDocument();
});
