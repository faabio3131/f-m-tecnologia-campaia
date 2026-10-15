import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { StrategyGenerateButton } from "@/components/StrategyGenerateButton";
import { setCsrfToken } from "@/lib/api/client";

const quote = { mode: "COMMERCIAL", action: "strategy", cycle_id: "cycle-a", policy_version: "v1", credits: 5, extra_amount: "2.00", included_available: 3 };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const props = () => ({ campaignId: "campaign-a", busy: false, hasPlan: false, onBusy: vi.fn(), onError: vi.fn(), onGenerated: vi.fn(async () => {}) });
beforeEach(() => setCsrfToken("csrf-strategy"));
afterEach(() => { vi.restoreAllMocks(); setCsrfToken(null); });

describe("Strategy credit confirmation", () => {
  it("quotes without executing and confirms the reviewed credits and estimated extras", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response(quote)).mockResolvedValueOnce(response({}));
    const callbacks = props(); const user = userEvent.setup();
    render(<StrategyGenerateButton {...callbacks} />);
    await user.click(screen.getByRole("button", { name: "Gerar estratégia" }));
    await screen.findByRole("region", { name: "Confirmar geração de estratégia" });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/5 créditos/)).toBeInTheDocument();
    expect(screen.getByText(/R\$ 2,00/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirmar geração" }));
    await waitFor(() => expect(callbacks.onGenerated).toHaveBeenCalledOnce());
    expect(JSON.parse(String(fetch.mock.calls[1][1]?.body))).toEqual({ credit_confirmation: {
      cycle_id: "cycle-a", policy_version: "v1", credits: 5, extra_amount: "2.00",
    } });
  });
  it("uncertain responses preserve the exact body and idempotency key", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response(quote))
      .mockRejectedValueOnce(new TypeError("connection lost")).mockResolvedValueOnce(response({}));
    const callbacks = props(); const user = userEvent.setup();
    render(<StrategyGenerateButton {...callbacks} />);
    await user.click(screen.getByRole("button", { name: "Gerar estratégia" }));
    await user.click(await screen.findByRole("button", { name: "Confirmar geração" }));
    await waitFor(() => expect(callbacks.onError).toHaveBeenCalledWith(expect.stringContaining("Resultado não confirmado")));
    await user.click(screen.getByRole("button", { name: "Confirmar geração" }));
    await waitFor(() => expect(callbacks.onGenerated).toHaveBeenCalledOnce());
    expect(fetch.mock.calls[1][1]?.body).toBe(fetch.mock.calls[2][1]?.body);
    expect(new Headers(fetch.mock.calls[1][1]?.headers).get("idempotency-key"))
      .toBe(new Headers(fetch.mock.calls[2][1]?.headers).get("idempotency-key"));
  });
  it("quota denial never dispatches a generation", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ code: "QUOTA_EXHAUSTED", message: "Sem franquia" }, 409));
    const callbacks = props(); const user = userEvent.setup();
    render(<StrategyGenerateButton {...callbacks} />);
    await user.click(screen.getByRole("button", { name: "Gerar estratégia" }));
    await waitFor(() => expect(callbacks.onError).toHaveBeenCalledWith("Sem franquia"));
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Confirmar geração" })).not.toBeInTheDocument();
  });
});
