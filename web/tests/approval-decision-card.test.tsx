import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApprovalDecisionCard } from "@/components/ApprovalDecisionCard";
import type { ApprovalRequest } from "@/contracts/types";

const PENDING_APPROVAL: ApprovalRequest = {
  id: "appr-1",
  campaign_id: "camp-1",
  reason: "Aprovacao necessaria para publicacao da campanha.",
  requested_by: "user-owner-1",
  plan_version: 1,
  status: "PENDING",
  requires_dual_approval: false,
  decided_by: [],
  created_at: "2026-01-01T00:00:00Z",
  expires_at: "2026-01-08T00:00:00Z",
};

const DECIDED_APPROVAL: ApprovalRequest = { ...PENDING_APPROVAL, status: "APPROVED" };

describe("ApprovalDecisionCard", () => {
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

  it("shows decision buttons for a PENDING approval", () => {
    render(<ApprovalDecisionCard bffOrigin="https://bff.example" approval={PENDING_APPROVAL} />);
    expect(screen.getByRole("button", { name: "Aprovar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rejeitar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pedir ajustes" })).toBeInTheDocument();
  });

  it("hides decision buttons for an already-decided approval", () => {
    render(<ApprovalDecisionCard bffOrigin="https://bff.example" approval={DECIDED_APPROVAL} />);
    expect(screen.queryByRole("button", { name: "Aprovar" })).not.toBeInTheDocument();
  });

  it("calls decision with CSRF, step-up, and idempotency headers, then reloads", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("location", { ...window.location, reload: vi.fn() });

    render(<ApprovalDecisionCard bffOrigin="https://bff.example" approval={PENDING_APPROVAL} />);
    await userEvent.click(screen.getByRole("button", { name: "Aprovar" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "https://bff.example/approvals/appr-1/decision",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": "real-csrf-token-value",
          "x-step-up-token": "web-ui-approval-decision-button-clicked",
          "idempotency-key": "fixed-idempotency-key",
        },
        body: JSON.stringify({ decision: "APPROVE" }),
      }),
    );
  });

  it("surfaces the self-approval rejection visibly on a 403 SEPARATION_OF_DUTIES", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ code: "SEPARATION_OF_DUTIES", message: "Quem propos..." }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ApprovalDecisionCard bffOrigin="https://bff.example" approval={PENDING_APPROVAL} />);
    await userEvent.click(screen.getByRole("button", { name: "Aprovar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Você não pode decidir sobre a sua própria proposta.",
    );
  });

  it("shows a generic error for a non-separation-of-duties failure", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ code: "VALIDATION_FAILED" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ApprovalDecisionCard bffOrigin="https://bff.example" approval={PENDING_APPROVAL} />);
    await userEvent.click(screen.getByRole("button", { name: "Rejeitar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível registrar a decisão. Tente novamente.",
    );
  });

  it("shows an error and never calls fetch when no CSRF cookie is present", async () => {
    document.cookie = "campaia_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<ApprovalDecisionCard bffOrigin="https://bff.example" approval={PENDING_APPROVAL} />);
    await userEvent.click(screen.getByRole("button", { name: "Pedir ajustes" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
