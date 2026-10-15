import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BillingUsagePanel } from "@/components/BillingUsagePanel";
import type { BillingUsage } from "@/contracts/types";
import { setCsrfToken } from "@/lib/api/client";

const usage: BillingUsage = {
  availability: "AVAILABLE", alerts: ["INCLUDED_80"], actions: [{ action: "strategy", credits: 5 }],
  cycle: { id: "cycle-a", trial: false, starts_at: "2026-10-15T12:00:00Z", ends_at: "2026-11-15T12:00:00Z", policy_version: "test-v1" },
  balance: { included_credits: 10, consumed_credits: 5, reserved_credits: 3, included_available: 2,
    extra_cap: "0.00", extra_credit_price: "1.00", extra_consumed_amount: "0.00", extra_committed_amount: "0.00", currency: "BRL" },
};
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
function stepUp(ready = true) {
  return { ready, testMode: true, headers: vi.fn(() => ({ "x-step-up-token": "test-proof" })), onIdToken: vi.fn(),
    consumePresentedToken: vi.fn(), noteError: vi.fn(), stepUpMessage: null };
}
beforeEach(() => setCsrfToken("csrf-test"));
afterEach(() => { vi.restoreAllMocks(); setCsrfToken(null); });

describe("Persisted credit usage", () => {
  it("separates delivered, reserved, available and extra cap without inventing provider costs", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response(usage));
    render(<BillingUsagePanel canManage={false} stepUp={stepUp()} />);
    const region = await screen.findByRole("region", { name: "Franquia do ciclo pago" });
    expect(within(region).getByText("Créditos reservados")).toBeInTheDocument();
    expect(within(region).getByText("Entregas consumidas")).toBeInTheDocument();
    expect(screen.getByText(/80% da franquia/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Revisar autorização/ })).not.toBeInTheDocument();
  });

  it("trial has no extras and unavailable has no fabricated balance", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ ...usage, cycle: { ...usage.cycle, trial: true } }));
    const view = render(<BillingUsagePanel canManage stepUp={stepUp()} />);
    await screen.findByText(/O teste não permite excedente/);
    expect(screen.queryByLabelText("Teto adicional por ciclo (R$)")).not.toBeInTheDocument();
    view.unmount();
    vi.mocked(globalThis.fetch).mockResolvedValue(response({ availability: "UNAVAILABLE", cycle: null, balance: null, alerts: [], actions: [] }));
    render(<BillingUsagePanel canManage stepUp={stepUp()} />);
    await screen.findByText("Medição de consumo ainda indisponível");
    expect(screen.queryByText("Franquia disponível")).not.toBeInTheDocument();
  });

  it("requires review and step-up and reuses the exact key/body after an uncertain response", async () => {
    const user = userEvent.setup();
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response(usage))
      .mockRejectedValueOnce(new TypeError("network failure"))
      .mockResolvedValueOnce(response({ ...usage, balance: { ...usage.balance, extra_cap: "50.00" } }));
    const proof = stepUp();
    render(<BillingUsagePanel canManage stepUp={proof} />);
    await screen.findByLabelText("Teto adicional por ciclo (R$)");
    await user.click(screen.getByRole("button", { name: "Revisar autorização de excedente" }));
    expect(fetch).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: "Confirmar autorização" }));
    await screen.findByText(/Resultado não confirmado/);
    await user.click(screen.getByRole("button", { name: "Confirmar autorização" }));
    await screen.findByText("Autorização de excedente registrada.");
    const first = fetch.mock.calls[1][1]!;
    const retry = fetch.mock.calls[2][1]!;
    expect(first.body).toBe(retry.body);
    expect(new Headers(first.headers).get("idempotency-key")).toBe(new Headers(retry.headers).get("idempotency-key"));
    expect(new Headers(first.headers).get("x-csrf-token")).toBe("csrf-test");
    expect(JSON.parse(String(first.body))).toEqual({ cap: "50.00", cycle_id: "cycle-a", policy_version: "test-v1", extra_credit_price: "1.00" });
  });

  it("prevents confirmation without recent authentication", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response(usage));
    const user = userEvent.setup();
    render(<BillingUsagePanel canManage stepUp={stepUp(false)} />);
    await screen.findByLabelText("Teto adicional por ciclo (R$)");
    await user.click(screen.getByRole("button", { name: "Revisar autorização de excedente" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Confirmar autorização" })).toBeDisabled());
  });
});
