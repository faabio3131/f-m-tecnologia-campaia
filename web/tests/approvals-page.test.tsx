import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { getServerSession, getServerApprovals, getPublicBffOrigin } = vi.hoisted(() => ({
  getServerSession: vi.fn(),
  getServerApprovals: vi.fn(),
  getPublicBffOrigin: vi.fn(),
}));

vi.mock("@/lib/session", () => ({
  getServerSession,
  getServerApprovals,
  getPublicBffOrigin,
}));

async function renderApprovalsPage() {
  const { default: ApprovalsPage } = await import("@/app/approvals/page");
  const element = await ApprovalsPage();
  render(element);
}

const ME = {
  user_id: "user-approver-1",
  tenant_id: "demo-tenant",
  business_unit_id: "bu-1",
  roles: ["APPROVER"],
  permissions: ["APPROVAL_DECIDE"],
  mfa_enabled: true,
};

const APPROVAL = {
  id: "appr-1",
  campaign_id: "camp-1",
  reason: "Aprovacao necessaria para publicacao da campanha.",
  requested_by: "user-owner-1",
  plan_version: 1,
  status: "PENDING" as const,
  requires_dual_approval: false,
  decided_by: [],
  created_at: "2026-01-01T00:00:00Z",
  expires_at: "2026-01-08T00:00:00Z",
};

describe("ApprovalsPage", () => {
  it("shows a configuration notice when NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN is unset", async () => {
    getPublicBffOrigin.mockReturnValue(undefined);
    getServerSession.mockResolvedValue(null);

    await renderApprovalsPage();

    expect(screen.getByText("Não configurado")).toBeInTheDocument();
  });

  it("shows a login link when there is no session", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(null);

    await renderApprovalsPage();

    const link = screen.getByRole("link", { name: "Entrar" });
    expect(link).toHaveAttribute(
      "href",
      "https://bff.example/auth/login?redirect_after_login=%2Fapprovals",
    );
    expect(getServerApprovals).not.toHaveBeenCalled();
  });

  it("shows an error state when approvals cannot be loaded", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerApprovals.mockResolvedValue(null);

    await renderApprovalsPage();

    expect(screen.getByText("Não foi possível carregar as aprovações")).toBeInTheDocument();
  });

  it("shows an empty note when there are no approvals", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerApprovals.mockResolvedValue([]);

    await renderApprovalsPage();

    expect(
      screen.getByText("Nenhuma aprovação pendente ou registrada ainda."),
    ).toBeInTheDocument();
  });

  it("renders a decision card per approval", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerApprovals.mockResolvedValue([APPROVAL]);

    await renderApprovalsPage();

    expect(
      screen.getByText("Aprovacao necessaria para publicacao da campanha."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aprovar" })).toBeInTheDocument();
  });
});
