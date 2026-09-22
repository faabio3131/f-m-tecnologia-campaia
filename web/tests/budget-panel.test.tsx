import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BudgetPanel } from "@/components/BudgetPanel";
import type { ApprovalRequest, Campaign } from "@/contracts/types";

// Real wire shape: budget.daily_cap (and every other monetary budget field) is a decimal
// string, matching the contract as corrected by the P-36 fix (missão de reconciliação,
// 22/09/2026) -- see BudgetPanel.tsx's own comment.
const BUDGET = {
  currency: "BRL",
  total_amount: "5000",
  daily_cap: "500",
  spent_to_date: "0",
} satisfies Campaign["budget"];

function approval(overrides: Partial<ApprovalRequest>): ApprovalRequest {
  return {
    id: "appr-1",
    campaign_id: "camp-1",
    kind: "BUDGET_CHANGE",
    reason: "Aprovacao necessaria para alteracao de orcamento.",
    requested_by: "user-owner-1",
    plan_version: 1,
    status: "PENDING",
    amount: "550",
    requires_dual_approval: false,
    decided_by: [],
    created_at: "2026-01-01T00:00:00Z",
    expires_at: "2026-01-08T00:00:00Z",
    ...overrides,
  };
}

describe("BudgetPanel", () => {
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

  it("shows the current budget and a propose form when there is no pending/approved change", () => {
    render(
      <BudgetPanel bffOrigin="https://bff.example" campaignId="camp-1" budget={BUDGET} approvals={[]} />,
    );
    expect(screen.getByText("BRL 5000")).toBeInTheDocument();
    expect(screen.getByText("BRL 500")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Propor alteração" })).toBeInTheDocument();
  });

  it("shows a pending note instead of the form when a PENDING budget-change approval exists for this campaign", () => {
    render(
      <BudgetPanel
        bffOrigin="https://bff.example"
        campaignId="camp-1"
        budget={BUDGET}
        approvals={[approval({ status: "PENDING" })]}
      />,
    );
    expect(screen.getByText(/aguardando aprovação/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Propor alteração" })).not.toBeInTheDocument();
  });

  it("ignores a PENDING approval for a different campaign or a different kind", () => {
    render(
      <BudgetPanel
        bffOrigin="https://bff.example"
        campaignId="camp-1"
        budget={BUDGET}
        approvals={[
          approval({ campaign_id: "camp-other" }),
          approval({ kind: "PUBLISH" }),
        ]}
      />,
    );
    expect(screen.getByRole("button", { name: "Propor alteração" })).toBeInTheDocument();
  });

  it("shows an 'Aplicar' button when an APPROVED change has a different amount than the current daily_cap", () => {
    render(
      <BudgetPanel
        bffOrigin="https://bff.example"
        campaignId="camp-1"
        budget={BUDGET}
        approvals={[approval({ status: "APPROVED", amount: "550" })]}
      />,
    );
    expect(screen.getByRole("button", { name: "Aplicar alteração" })).toBeInTheDocument();
  });

  it("treats an APPROVED change whose amount already equals daily_cap as already applied", () => {
    render(
      <BudgetPanel
        bffOrigin="https://bff.example"
        campaignId="camp-1"
        budget={BUDGET}
        approvals={[approval({ status: "APPROVED", amount: "500" })]}
      />,
    );
    expect(screen.queryByRole("button", { name: "Aplicar alteração" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Propor alteração" })).toBeInTheDocument();
  });

  it("proposes a change via POST /approvals with campaign_id/kind/amount, then reloads", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 201 });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("location", { ...window.location, reload: vi.fn() });

    render(
      <BudgetPanel bffOrigin="https://bff.example" campaignId="camp-1" budget={BUDGET} approvals={[]} />,
    );
    await userEvent.type(screen.getByLabelText("Propor novo teto diário"), "550");
    await userEvent.click(screen.getByRole("button", { name: "Propor alteração" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "https://bff.example/approvals",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json", "x-csrf-token": "real-csrf-token-value" },
        body: JSON.stringify({ campaign_id: "camp-1", kind: "BUDGET_CHANGE", amount: "550" }),
      }),
    );
  });

  it("applies an approved change via PATCH with CSRF, step-up, and idempotency headers, then reloads", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 202 });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("location", { ...window.location, reload: vi.fn() });

    render(
      <BudgetPanel
        bffOrigin="https://bff.example"
        campaignId="camp-1"
        budget={BUDGET}
        approvals={[approval({ status: "APPROVED", amount: "550" })]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Aplicar alteração" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "https://bff.example/campaigns/camp-1/budget",
      expect.objectContaining({
        method: "PATCH",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": "real-csrf-token-value",
          "x-step-up-token": "web-ui-apply-budget-change-button-clicked",
          "idempotency-key": "fixed-idempotency-key",
        },
        body: JSON.stringify({ daily_cap: "550", approval_id: "appr-1" }),
      }),
    );
  });

  it("surfaces the BUDGET_LIMIT rejection message when applying fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ code: "BUDGET_LIMIT", message: "Variação de 100% excede o máximo de 20%." }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <BudgetPanel
        bffOrigin="https://bff.example"
        campaignId="camp-1"
        budget={BUDGET}
        approvals={[approval({ status: "APPROVED", amount: "1000" })]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Aplicar alteração" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Variação de 100% excede o máximo de 20%.",
    );
  });

  it("shows an error and never calls fetch when no CSRF cookie is present", async () => {
    document.cookie = "campaia_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(
      <BudgetPanel bffOrigin="https://bff.example" campaignId="camp-1" budget={BUDGET} approvals={[]} />,
    );
    await userEvent.type(screen.getByLabelText("Propor novo teto diário"), "550");
    await userEvent.click(screen.getByRole("button", { name: "Propor alteração" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
