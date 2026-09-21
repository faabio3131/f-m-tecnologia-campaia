import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const {
  getServerSession,
  getServerBrandProfiles,
  getServerConnections,
  getPublicBffOrigin,
} = vi.hoisted(() => ({
  getServerSession: vi.fn(),
  getServerBrandProfiles: vi.fn(),
  getServerConnections: vi.fn(),
  getPublicBffOrigin: vi.fn(),
}));

vi.mock("@/lib/session", () => ({
  getServerSession,
  getServerBrandProfiles,
  getServerConnections,
  getPublicBffOrigin,
}));

// OnboardingPage is an async Server Component -- same pattern as tests/dashboard-page.test.tsx.
async function renderOnboardingPage() {
  const { default: OnboardingPage } = await import("@/app/onboarding/page");
  const element = await OnboardingPage();
  render(element);
}

const ME = {
  user_id: "user-owner-1",
  tenant_id: "demo-tenant",
  business_unit_id: "bu-1",
  roles: ["OWNER"],
  permissions: ["BRAND_MANAGE", "CONNECTION_MANAGE"],
  mfa_enabled: true,
};

const CONNECTION = {
  id: "conn-1",
  provider: "GOOGLE_ADS" as const,
  external_account_id: "acc-1",
  display_name: "Google Ads (simulado)",
  status: "ACTIVE" as const,
  api_version: "sim-1",
  last_synced_at: "2026-01-01T00:00:00Z",
};

describe("OnboardingPage", () => {
  it("shows a configuration notice when NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN is unset", async () => {
    getPublicBffOrigin.mockReturnValue(undefined);
    getServerSession.mockResolvedValue(null);

    await renderOnboardingPage();

    expect(screen.getByText("Não configurado")).toBeInTheDocument();
    expect(getServerSession).not.toHaveBeenCalled();
  });

  it("shows a login link when there is no session", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(null);

    await renderOnboardingPage();

    expect(screen.getByText("Você não está autenticado")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Entrar" });
    expect(link).toHaveAttribute(
      "href",
      "https://bff.example/auth/login?redirect_after_login=%2Fonboarding",
    );
    expect(getServerBrandProfiles).not.toHaveBeenCalled();
  });

  it("shows an error state when brand profiles or connections cannot be loaded", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerBrandProfiles.mockResolvedValue(null);
    getServerConnections.mockResolvedValue([]);

    await renderOnboardingPage();

    expect(
      screen.getByText("Não foi possível carregar os dados do onboarding"),
    ).toBeInTheDocument();
  });

  it("shows the Connect Accounts cards, empty Brand Kit note, and a disabled finish note with zero connections", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerBrandProfiles.mockResolvedValue([]);
    getServerConnections.mockResolvedValue([]);

    await renderOnboardingPage();

    expect(screen.getByText("Google Ads")).toBeInTheDocument();
    expect(screen.getByText("Meta (Facebook/Instagram)")).toBeInTheDocument();
    expect(screen.getByText("WhatsApp Business")).toBeInTheDocument();
    expect(screen.getAllByText("Não conectado")).toHaveLength(3);
    expect(screen.getByText(/Nenhum Brand Kit ainda/)).toBeInTheDocument();
    expect(
      screen.getByText("Conecte ao menos uma conta para concluir o onboarding."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Concluir Onboarding" })).not.toBeInTheDocument();
  });

  it("enables 'Concluir Onboarding' once at least one channel is connected", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerBrandProfiles.mockResolvedValue([]);
    getServerConnections.mockResolvedValue([CONNECTION]);

    await renderOnboardingPage();

    expect(screen.getByText("Conectado (simulado)")).toBeInTheDocument();
    const finishLink = screen.getByRole("link", { name: "Concluir Onboarding" });
    expect(finishLink).toHaveAttribute("href", "/dashboard");
    expect(
      screen.queryByText("Conecte ao menos uma conta para concluir o onboarding."),
    ).not.toBeInTheDocument();
  });
});
