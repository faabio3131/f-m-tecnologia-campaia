import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { getServerSession, getServerCampaigns, getPublicBffOrigin } = vi.hoisted(() => ({
  getServerSession: vi.fn(),
  getServerCampaigns: vi.fn(),
  getPublicBffOrigin: vi.fn(),
}));

vi.mock("@/lib/session", () => ({
  getServerSession,
  getServerCampaigns,
  getPublicBffOrigin,
}));

// CampaignsPage renders BriefForm, a Client Component that calls next/navigation's
// useRouter() -- unavailable outside a real App Router tree, same as any other Client
// Component test needing this mock (see tests/brief-form.test.tsx).
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

async function renderCampaignsPage() {
  const { default: CampaignsPage } = await import("@/app/campaigns/page");
  const element = await CampaignsPage();
  render(element);
}

const ME = {
  user_id: "user-owner-1",
  tenant_id: "demo-tenant",
  business_unit_id: "bu-1",
  roles: ["OWNER"],
  permissions: ["CAMPAIGN_CREATE"],
  mfa_enabled: true,
};

const CAMPAIGN = {
  id: "camp-1",
  business_unit_id: "bu-1",
  name: "Tênis de corrida",
  objective: "Gerar leads",
  state: "DRAFT" as const,
  channels: ["GOOGLE_ADS" as const],
  external_resources: [],
  budget: { currency: "BRL", total_amount: 5000, daily_cap: 500, spent_to_date: 0 },
  created_at: "2026-01-01T00:00:00Z",
};

describe("CampaignsPage", () => {
  it("shows a configuration notice when NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN is unset", async () => {
    getPublicBffOrigin.mockReturnValue(undefined);
    getServerSession.mockResolvedValue(null);

    await renderCampaignsPage();

    expect(screen.getByText("Não configurado")).toBeInTheDocument();
    expect(getServerSession).not.toHaveBeenCalled();
  });

  it("shows a login link when there is no session", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(null);

    await renderCampaignsPage();

    const link = screen.getByRole("link", { name: "Entrar" });
    expect(link).toHaveAttribute(
      "href",
      "https://bff.example/auth/login?redirect_after_login=%2Fcampaigns",
    );
    expect(getServerCampaigns).not.toHaveBeenCalled();
  });

  it("shows an error state when campaigns cannot be loaded", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerCampaigns.mockResolvedValue(null);

    await renderCampaignsPage();

    expect(screen.getByText("Não foi possível carregar as campanhas")).toBeInTheDocument();
  });

  it("shows an empty note and the brief form when there are no campaigns yet", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerCampaigns.mockResolvedValue([]);

    await renderCampaignsPage();

    expect(
      screen.getByText("Nenhuma campanha ainda — submeta o primeiro briefing acima."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enviar briefing" })).toBeInTheDocument();
  });

  it("lists existing campaigns linked to their detail page", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerCampaigns.mockResolvedValue([CAMPAIGN]);

    await renderCampaignsPage();

    const link = screen.getByRole("link", { name: /Tênis de corrida/ });
    expect(link).toHaveAttribute("href", "/campaigns/camp-1");
    expect(screen.getByText("DRAFT")).toBeInTheDocument();
  });
});
