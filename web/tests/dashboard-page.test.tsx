import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { getServerSession, getServerSessionMemberships, getPublicBffOrigin } = vi.hoisted(
  () => ({
    getServerSession: vi.fn(),
    getServerSessionMemberships: vi.fn(),
    getPublicBffOrigin: vi.fn(),
  }),
);

vi.mock("@/lib/session", () => ({
  getServerSession,
  getServerSessionMemberships,
  getPublicBffOrigin,
}));

// DashboardPage is an async Server Component -- same pattern as tests/account-page.test.tsx.
async function renderDashboardPage() {
  const { default: DashboardPage } = await import("@/app/dashboard/page");
  const element = await DashboardPage();
  render(element);
}

const ME = {
  user_id: "user-owner-3",
  tenant_id: "demo-tenant",
  business_unit_id: "bu-1",
  roles: ["OWNER"],
  permissions: ["CAMPAIGN_VIEW"],
  mfa_enabled: true,
};

describe("DashboardPage", () => {
  it("shows a configuration notice when NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN is unset", async () => {
    getPublicBffOrigin.mockReturnValue(undefined);
    getServerSession.mockResolvedValue(null);

    await renderDashboardPage();

    expect(screen.getByText("Não configurado")).toBeInTheDocument();
    expect(getServerSession).not.toHaveBeenCalled();
  });

  it("shows a login link when there is no session", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(null);

    await renderDashboardPage();

    expect(screen.getByText("Você não está autenticado")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Entrar" });
    expect(link).toHaveAttribute(
      "href",
      "https://bff.example/auth/login?redirect_after_login=%2Fdashboard",
    );
    expect(getServerSessionMemberships).not.toHaveBeenCalled();
  });

  it("shows an error state when memberships cannot be loaded despite a valid session", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerSessionMemberships.mockResolvedValue(null);

    await renderDashboardPage();

    expect(
      screen.getByText("Não foi possível carregar os memberships da sessão"),
    ).toBeInTheDocument();
  });

  it("renders the shell without a tenant switcher for a single-membership session", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerSessionMemberships.mockResolvedValue({
      memberships: [
        { tenant_id: "demo-tenant", business_unit_id: "bu-1", roles: ["OWNER"], is_active: true },
      ],
    });

    await renderDashboardPage();

    expect(screen.getByText("user-owner-3")).toBeInTheDocument();
    expect(screen.queryByLabelText("Tenant ativo")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sair" })).toBeInTheDocument();
    expect(screen.getByText("Nenhuma funcionalidade de negócio ainda")).toBeInTheDocument();
  });

  it("renders the tenant switcher for a multi-membership session", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerSessionMemberships.mockResolvedValue({
      memberships: [
        { tenant_id: "demo-tenant", business_unit_id: "bu-1", roles: ["OWNER"], is_active: true },
        { tenant_id: "other-tenant", business_unit_id: "bu-2", roles: ["VIEWER"], is_active: false },
      ],
    });

    await renderDashboardPage();

    expect(screen.getByLabelText("Tenant ativo")).toBeInTheDocument();
  });
});
