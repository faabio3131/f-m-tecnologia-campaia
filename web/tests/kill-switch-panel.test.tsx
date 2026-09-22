import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { KillSwitchPanel } from "@/components/KillSwitchPanel";
import type { Campaign } from "@/contracts/types";

const CAMPAIGN_1: Campaign = {
  id: "camp-1",
  business_unit_id: "bu-1",
  name: "Campanha 1",
  objective: "Objetivo",
  state: "ACTIVE",
  channels: ["GOOGLE_ADS"],
  external_resources: [],
  budget: { currency: "BRL", total_amount: "5000", daily_cap: "500", spent_to_date: "0" },
  created_at: "2026-01-01T00:00:00Z",
};

const CAMPAIGN_2: Campaign = {
  ...CAMPAIGN_1,
  id: "camp-2",
  name: "Campanha 2",
};

describe("KillSwitchPanel", () => {
  const originalCookie = document.cookie;

  beforeEach(() => {
    document.cookie = "campaia_csrf=real-csrf-token-value";
    vi.stubGlobal("crypto", { randomUUID: () => "fixed-idempotency-key" });
  });

  afterEach(() => {
    document.cookie = originalCookie;
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("defaults to CAMPAIGN scope with the first campaign selected", () => {
    render(
      <KillSwitchPanel bffOrigin="https://bff.example" campaigns={[CAMPAIGN_1, CAMPAIGN_2]} />,
    );
    expect(screen.getByRole("radio", { name: "Uma campanha" })).toBeChecked();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it("hides the campaign selector and shows a note when there are no campaigns", () => {
    render(<KillSwitchPanel bffOrigin="https://bff.example" campaigns={[]} />);
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByText("Nenhuma campanha disponível para este escopo.")).toBeInTheDocument();
  });

  it("hides the campaign selector when TENANT scope is chosen", async () => {
    render(<KillSwitchPanel bffOrigin="https://bff.example" campaigns={[CAMPAIGN_1]} />);
    await userEvent.click(screen.getByRole("radio", { name: "Todo o tenant" }));
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("shows an error and never calls fetch when the reason is empty", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<KillSwitchPanel bffOrigin="https://bff.example" campaigns={[CAMPAIGN_1]} />);
    await userEvent.click(screen.getByRole("button", { name: "Acionar parada de emergência" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Informe o motivo da parada de emergência.",
    );
  });

  it("posts CAMPAIGN scope via POST /kill-switch with CSRF and idempotency headers, then shows the result", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ scope: "CAMPAIGN", affected_campaign_ids: ["camp-1"] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <KillSwitchPanel bffOrigin="https://bff.example" campaigns={[CAMPAIGN_1, CAMPAIGN_2]} />,
    );
    await userEvent.type(screen.getByLabelText("Motivo"), "Gasto acima do esperado");
    await userEvent.click(screen.getByRole("button", { name: "Acionar parada de emergência" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "https://bff.example/kill-switch",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": "real-csrf-token-value",
          "idempotency-key": "fixed-idempotency-key",
        },
        body: JSON.stringify({
          scope: "CAMPAIGN",
          target_id: "camp-1",
          reason: "Gasto acima do esperado",
        }),
      }),
    );
    expect(await screen.findByText(/Escopo CAMPAIGN/)).toBeInTheDocument();
    expect(screen.getByText(/campanhas afetadas: camp-1\./)).toBeInTheDocument();
  });

  it("posts TENANT scope with target_id null", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ scope: "TENANT", affected_campaign_ids: ["camp-1", "camp-2"] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<KillSwitchPanel bffOrigin="https://bff.example" campaigns={[CAMPAIGN_1]} />);
    await userEvent.click(screen.getByRole("radio", { name: "Todo o tenant" }));
    await userEvent.type(screen.getByLabelText("Motivo"), "Incidente externo");
    await userEvent.click(screen.getByRole("button", { name: "Acionar parada de emergência" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "https://bff.example/kill-switch",
      expect.objectContaining({
        body: JSON.stringify({ scope: "TENANT", target_id: null, reason: "Incidente externo" }),
      }),
    );
  });

  it("shows a note when no campaign was affected", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ scope: "TENANT", affected_campaign_ids: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<KillSwitchPanel bffOrigin="https://bff.example" campaigns={[CAMPAIGN_1]} />);
    await userEvent.click(screen.getByRole("radio", { name: "Todo o tenant" }));
    await userEvent.type(screen.getByLabelText("Motivo"), "Teste");
    await userEvent.click(screen.getByRole("button", { name: "Acionar parada de emergência" }));

    expect(
      await screen.findByText(/nenhuma campanha estava em estado pausável/),
    ).toBeInTheDocument();
  });

  it("shows an error and never calls fetch when no CSRF cookie is present", async () => {
    document.cookie = "campaia_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<KillSwitchPanel bffOrigin="https://bff.example" campaigns={[CAMPAIGN_1]} />);
    await userEvent.type(screen.getByLabelText("Motivo"), "Teste");
    await userEvent.click(screen.getByRole("button", { name: "Acionar parada de emergência" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Sessão sem cookie CSRF válido — recarregue a página.",
    );
  });

  it("shows an error message when the request fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 403 });
    vi.stubGlobal("fetch", fetchMock);

    render(<KillSwitchPanel bffOrigin="https://bff.example" campaigns={[CAMPAIGN_1]} />);
    await userEvent.type(screen.getByLabelText("Motivo"), "Teste");
    await userEvent.click(screen.getByRole("button", { name: "Acionar parada de emergência" }));

    expect(
      await screen.findByText("Não foi possível acionar a parada de emergência. Tente novamente."),
    ).toBeInTheDocument();
  });
});
