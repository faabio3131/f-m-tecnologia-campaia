import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AutonomyPanel } from "@/components/AutonomyPanel";
import type { ApprovalRequest, AutonomySettings, Campaign } from "@/contracts/types";

const AUTONOMY: AutonomySettings = {
  level: 1,
  level_label: "APROVADO",
  max_level_allowed: 2,
  always_require_human: ["FIRST_PUBLISH", "AUTONOMY_CHANGE"],
  max_budget_change_pct: 10,
  updated_at: "2026-01-01T00:00:00Z",
};

const CAMPAIGN: Campaign = {
  id: "camp-1",
  business_unit_id: "bu-1",
  name: "Campanha 1",
  objective: "Objetivo",
  state: "DRAFT",
  channels: ["GOOGLE_ADS"],
  external_resources: [],
  budget: { currency: "BRL", total_amount: "5000", daily_cap: "500", spent_to_date: "0" },
  created_at: "2026-01-01T00:00:00Z",
};

function approval(overrides: Partial<ApprovalRequest>): ApprovalRequest {
  return {
    id: "appr-1",
    campaign_id: "camp-1",
    kind: "AUTONOMY_CHANGE",
    reason: "Aprovacao necessaria para alteracao de nivel de autonomia.",
    requested_by: "user-owner-1",
    plan_version: 1,
    status: "PENDING",
    amount: "2",
    requires_dual_approval: false,
    decided_by: [],
    created_at: "2026-01-01T00:00:00Z",
    expires_at: "2026-01-08T00:00:00Z",
    ...overrides,
  };
}

describe("AutonomyPanel", () => {
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

  it("shows the current level, ceiling, and always-require-human triggers", () => {
    render(
      <AutonomyPanel
        bffOrigin="https://bff.example"
        autonomy={AUTONOMY}
        approvals={[]}
        campaigns={[CAMPAIGN]}
      />,
    );
    // "1 — APROVADO" also appears as a selectable radio option label below the summary
    // (level 1 is within the contracted ceiling), so scope this query to the summary <dl>.
    const summary = screen.getByText("Nível atual").closest("dl") as HTMLElement;
    expect(within(summary).getByText("1 — APROVADO")).toBeInTheDocument();
    expect(within(summary).getByText("2")).toBeInTheDocument();
    expect(screen.getByText("FIRST_PUBLISH")).toBeInTheDocument();
    expect(screen.getByText("AUTONOMY_CHANGE")).toBeInTheDocument();
  });

  it("disables levels above the contracted ceiling", () => {
    render(
      <AutonomyPanel
        bffOrigin="https://bff.example"
        autonomy={AUTONOMY}
        approvals={[]}
        campaigns={[CAMPAIGN]}
      />,
    );
    const operacional = screen.getByRole("radio", { name: /3 — OPERACIONAL/ });
    expect(operacional).toBeDisabled();
    const limitado = screen.getByRole("radio", { name: /2 — LIMITADO/ });
    expect(limitado).not.toBeDisabled();
  });

  it("shows a disabled note instead of the form when there is no campaign yet", () => {
    render(
      <AutonomyPanel
        bffOrigin="https://bff.example"
        autonomy={AUTONOMY}
        approvals={[]}
        campaigns={[]}
      />,
    );
    expect(
      screen.getByText(
        "É necessário ter ao menos uma campanha para propor uma alteração de autonomia.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Propor alteração" })).not.toBeInTheDocument();
  });

  it("shows a pending note when a PENDING autonomy approval exists", () => {
    render(
      <AutonomyPanel
        bffOrigin="https://bff.example"
        autonomy={AUTONOMY}
        approvals={[approval({ status: "PENDING", amount: "2" })]}
        campaigns={[CAMPAIGN]}
      />,
    );
    expect(screen.getByText(/aguardando aprovação/)).toBeInTheDocument();
  });

  it("ignores approvals of a different kind", () => {
    render(
      <AutonomyPanel
        bffOrigin="https://bff.example"
        autonomy={AUTONOMY}
        approvals={[approval({ kind: "BUDGET_CHANGE", status: "PENDING" })]}
        campaigns={[CAMPAIGN]}
      />,
    );
    expect(screen.getByRole("button", { name: "Propor alteração" })).toBeInTheDocument();
  });

  it("shows an 'Aplicar' button when an APPROVED change differs from the current level", () => {
    render(
      <AutonomyPanel
        bffOrigin="https://bff.example"
        autonomy={AUTONOMY}
        approvals={[approval({ status: "APPROVED", amount: "2" })]}
        campaigns={[CAMPAIGN]}
      />,
    );
    expect(screen.getByRole("button", { name: "Aplicar alteração" })).toBeInTheDocument();
  });

  it("treats an APPROVED change whose amount already equals the current level as already applied", () => {
    render(
      <AutonomyPanel
        bffOrigin="https://bff.example"
        autonomy={AUTONOMY}
        approvals={[approval({ status: "APPROVED", amount: "1" })]}
        campaigns={[CAMPAIGN]}
      />,
    );
    expect(screen.queryByRole("button", { name: "Aplicar alteração" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Propor alteração" })).toBeInTheDocument();
  });

  it("proposes a level via POST /approvals with campaign_id/kind/amount, then reloads", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 201 });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("location", { ...window.location, reload: vi.fn() });

    render(
      <AutonomyPanel
        bffOrigin="https://bff.example"
        autonomy={AUTONOMY}
        approvals={[]}
        campaigns={[CAMPAIGN]}
      />,
    );
    await userEvent.click(screen.getByRole("radio", { name: /2 — LIMITADO/ }));
    await userEvent.click(screen.getByRole("button", { name: "Propor alteração" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "https://bff.example/approvals",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json", "x-csrf-token": "real-csrf-token-value" },
        body: JSON.stringify({ campaign_id: "camp-1", kind: "AUTONOMY_CHANGE", amount: 2 }),
      }),
    );
  });

  it("applies an approved change via PUT with CSRF, step-up, and idempotency headers, then reloads", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("location", { ...window.location, reload: vi.fn() });

    render(
      <AutonomyPanel
        bffOrigin="https://bff.example"
        autonomy={AUTONOMY}
        approvals={[approval({ status: "APPROVED", amount: "2" })]}
        campaigns={[CAMPAIGN]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Aplicar alteração" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "https://bff.example/autonomy",
      expect.objectContaining({
        method: "PUT",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": "real-csrf-token-value",
          "x-step-up-token": "web-ui-apply-autonomy-change-button-clicked",
          "idempotency-key": "fixed-idempotency-key",
        },
        body: JSON.stringify({ level: 2, approval_id: "appr-1" }),
      }),
    );
  });

  it("shows an error and never calls fetch when no CSRF cookie is present", async () => {
    document.cookie = "campaia_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(
      <AutonomyPanel
        bffOrigin="https://bff.example"
        autonomy={AUTONOMY}
        approvals={[]}
        campaigns={[CAMPAIGN]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Propor alteração" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
