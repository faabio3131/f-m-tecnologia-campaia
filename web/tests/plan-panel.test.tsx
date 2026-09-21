import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PlanPanel } from "@/components/PlanPanel";
import type { CampaignPlan } from "@/contracts/types";

const NO_PLAN: CampaignPlan = { campaign_id: "camp-1", plan_version: 0, plan: null };
const WITH_PLAN: CampaignPlan = {
  campaign_id: "camp-1",
  plan_version: 1,
  plan: {
    proposal_id: "prop-1",
    // Real shape (backend/campaia_core/agents.py AGENTS["strategist"].output_schema) --
    // a structured object, not free text. See the module comment in
    // src/contracts/types.ts (StrategistPlanOutput) for how this was found.
    output: {
      objetivo: "Gerar leads qualificados",
      funil: "TOFU",
      canais: ["GOOGLE_ADS"],
      justificativa: "Alcance amplo com baixo custo por lead.",
    },
    provider: "SIMULATOR",
    model: "sim-strategist-1",
  },
};

describe("PlanPanel", () => {
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

  it("shows an empty note and 'Gerar estratégia' when no plan exists yet", () => {
    render(<PlanPanel bffOrigin="https://bff.example" campaignId="camp-1" plan={NO_PLAN} />);
    expect(
      screen.getByText("Nenhuma estratégia gerada ainda para esta campanha."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Gerar estratégia" })).toBeInTheDocument();
  });

  it("shows the plan output fields and 'Regenerar estratégia' when a plan exists", () => {
    render(<PlanPanel bffOrigin="https://bff.example" campaignId="camp-1" plan={WITH_PLAN} />);
    expect(screen.getByText("Gerar leads qualificados")).toBeInTheDocument();
    expect(screen.getByText("TOFU")).toBeInTheDocument();
    expect(screen.getByText("GOOGLE_ADS")).toBeInTheDocument();
    expect(screen.getByText("Alcance amplo com baixo custo por lead.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Regenerar estratégia" })).toBeInTheDocument();
  });

  it("calls plan/regenerate with CSRF and idempotency headers, then reloads", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 202 });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("location", { ...window.location, reload: vi.fn() });

    render(<PlanPanel bffOrigin="https://bff.example" campaignId="camp-1" plan={NO_PLAN} />);
    await userEvent.click(screen.getByRole("button", { name: "Gerar estratégia" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "https://bff.example/campaigns/camp-1/plan/regenerate",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": "real-csrf-token-value",
          "idempotency-key": "fixed-idempotency-key",
        },
        body: JSON.stringify({}),
      }),
    );
  });

  it("sends adjustments text when provided", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 202 });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("location", { ...window.location, reload: vi.fn() });

    render(<PlanPanel bffOrigin="https://bff.example" campaignId="camp-1" plan={WITH_PLAN} />);
    await userEvent.type(
      screen.getByLabelText("Ajustes para a próxima geração (opcional)"),
      "focar em remarketing",
    );
    await userEvent.click(screen.getByRole("button", { name: "Regenerar estratégia" }));

    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body).toEqual({ adjustments: "focar em remarketing" });
  });

  it("shows an error and never calls fetch when no CSRF cookie is present", async () => {
    document.cookie = "campaia_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<PlanPanel bffOrigin="https://bff.example" campaignId="camp-1" plan={NO_PLAN} />);
    await userEvent.click(screen.getByRole("button", { name: "Gerar estratégia" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("shows an error when the request fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 409 });
    vi.stubGlobal("fetch", fetchMock);

    render(<PlanPanel bffOrigin="https://bff.example" campaignId="camp-1" plan={NO_PLAN} />);
    await userEvent.click(screen.getByRole("button", { name: "Gerar estratégia" }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
