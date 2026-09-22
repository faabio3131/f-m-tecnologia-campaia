import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { getServerSession, getPublicBffOrigin } = vi.hoisted(() => ({
  getServerSession: vi.fn(),
  getPublicBffOrigin: vi.fn(),
}));

vi.mock("@/lib/session", () => ({ getServerSession, getPublicBffOrigin }));

// AccountPage is an async Server Component -- rendered by awaiting the function itself
// and passing the resolved element tree to Testing Library, since Next.js Server
// Components are not plain synchronous React components.
async function renderAccountPage() {
  const { default: AccountPage } = await import("@/app/account/page");
  const element = await AccountPage();
  render(element);
}

describe("AccountPage", () => {
  it("shows a configuration notice when NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN is unset", async () => {
    getPublicBffOrigin.mockReturnValue(undefined);
    getServerSession.mockResolvedValue(null);

    await renderAccountPage();

    expect(screen.getByText("Não configurado")).toBeInTheDocument();
    expect(getServerSession).not.toHaveBeenCalled();
  });

  it("shows a login link (pointing at the real BFF) when there is no session", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(null);

    await renderAccountPage();

    expect(screen.getByText("Você não está autenticado")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Entrar" });
    expect(link).toHaveAttribute(
      "href",
      "https://bff.example/auth/login?redirect_after_login=%2Faccount",
    );
  });

  it("shows real session data and a logout control when a session exists", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue({
      user_id: "user-owner-1",
      tenant_id: "demo-tenant",
      business_unit_id: "bu-1",
      roles: ["OWNER"],
      permissions: ["CAMPAIGN_VIEW"],
      mfa_enabled: true,
    });

    await renderAccountPage();

    expect(screen.getByText("Sessão real ativa")).toBeInTheDocument();
    expect(screen.getByText("user-owner-1")).toBeInTheDocument();
    expect(screen.getByText("demo-tenant")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sair" })).toBeInTheDocument();
  });
});
