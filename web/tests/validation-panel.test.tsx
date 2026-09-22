import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ValidationPanel } from "@/components/ValidationPanel";

const APPROVABLE_DECISION = {
  policy_decision_id: "pd-1",
  outcome: "APPROVABLE",
  requires_human_approval: true,
  requires_dual_approval: false,
  findings: [{ code: "OK", severity: "INFO", explanation: "Tudo certo." }],
};

const BLOCKED_DECISION = {
  policy_decision_id: null,
  outcome: "BLOCKED",
  requires_human_approval: false,
  requires_dual_approval: false,
  findings: [{ code: "BUDGET_EXCEEDED", severity: "BLOCKING", explanation: "Orçamento excedido." }],
};

describe("ValidationPanel", () => {
  const originalCookie = document.cookie;

  beforeEach(() => {
    document.cookie = "campaia_csrf=real-csrf-token-value";
  });

  afterEach(() => {
    document.cookie = originalCookie;
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("calls validate with the CSRF header and shows the outcome + findings", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => APPROVABLE_DECISION });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ValidationPanel
        bffOrigin="https://bff.example"
        campaignId="camp-1"
        hasPendingApproval={false}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Validar" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "https://bff.example/campaigns/camp-1/validate",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: { "x-csrf-token": "real-csrf-token-value" },
      }),
    );
    expect(await screen.findByText("APPROVABLE")).toBeInTheDocument();
    expect(screen.getByText(/Tudo certo\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Solicitar aprovação" })).toBeInTheDocument();
  });

  it("shows a note instead of a button when approval is already pending", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => APPROVABLE_DECISION });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ValidationPanel
        bffOrigin="https://bff.example"
        campaignId="camp-1"
        hasPendingApproval={true}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Validar" }));

    expect(await screen.findByText("Aprovação já solicitada — aguardando decisão.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Solicitar aprovação" })).not.toBeInTheDocument();
  });

  it("does not offer a request-approval button when human approval is not required", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => BLOCKED_DECISION });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ValidationPanel
        bffOrigin="https://bff.example"
        campaignId="camp-1"
        hasPendingApproval={false}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Validar" }));

    expect(await screen.findByText("BLOCKED")).toBeInTheDocument();
    expect(
      screen.getByText("Esta campanha não exige aprovação humana."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Solicitar aprovação" })).not.toBeInTheDocument();
  });

  it("requests approval with campaign_id/kind/requires_dual_approval, then reloads", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => APPROVABLE_DECISION })
      .mockResolvedValueOnce({ ok: true, status: 201 });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("location", { ...window.location, reload: vi.fn() });

    render(
      <ValidationPanel
        bffOrigin="https://bff.example"
        campaignId="camp-1"
        hasPendingApproval={false}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Validar" }));
    await userEvent.click(await screen.findByRole("button", { name: "Solicitar aprovação" }));

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://bff.example/approvals",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json", "x-csrf-token": "real-csrf-token-value" },
        body: JSON.stringify({
          campaign_id: "camp-1",
          kind: "PUBLISH",
          requires_dual_approval: false,
        }),
      }),
    );
  });

  it("shows an error when validate fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 409 });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ValidationPanel
        bffOrigin="https://bff.example"
        campaignId="camp-1"
        hasPendingApproval={false}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Validar" }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
