import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const {
  getServerSession,
  getServerCampaign,
  getServerPlan,
  getServerApprovals,
  getPublicBffOrigin,
} = vi.hoisted(() => ({
  getServerSession: vi.fn(),
  getServerCampaign: vi.fn(),
  getServerPlan: vi.fn(),
  getServerApprovals: vi.fn(),
  getPublicBffOrigin: vi.fn(),
}));

vi.mock("@/lib/session", () => ({
  getServerSession,
  getServerCampaign,
  getServerPlan,
  getServerApprovals,
  getPublicBffOrigin,
}));

async function renderCampaignDetailPage(campaignId = "camp-1") {
  const { default: CampaignDetailPage } = await import("@/app/campaigns/[campaignId]/page");
  const element = await CampaignDetailPage({ params: Promise.resolve({ campaignId }) });
  render(element);
}

const ME = {
  user_id: "user-owner-1",
  tenant_id: "demo-tenant",
  business_unit_id: "bu-1",
  roles: ["OWNER"],
  permissions: ["CAMPAIGN_EDIT"],
  mfa_enabled: true,
};

const CAMPAIGN = {
  id: "camp-1",
  business_unit_id: "bu-1",
  name: "Tênis de corrida",
  objective: "Gerar leads qualificados",
  state: "DRAFT" as const,
  channels: ["GOOGLE_ADS" as const],
  external_resources: [],
  budget: { currency: "BRL", total_amount: 5000, daily_cap: 500, spent_to_date: 0 },
  created_at: "2026-01-01T00:00:00Z",
};

const NO_PLAN = { campaign_id: "camp-1", plan_version: 0, plan: null };

const PENDING_APPROVAL_ELSEWHERE = {
  id: "appr-other",
  campaign_id: "camp-other",
  reason: "Aprovacao necessaria para publicacao da campanha.",
  requested_by: "user-owner-1",
  plan_version: 1,
  status: "PENDING" as const,
  requires_dual_approval: false,
  decided_by: [],
  created_at: "2026-01-01T00:00:00Z",
  expires_at: "2026-01-08T00:00:00Z",
};

const PENDING_APPROVAL_THIS_CAMPAIGN = { ...PENDING_APPROVAL_ELSEWHERE, id: "appr-1", campaign_id: "camp-1" };

describe("CampaignDetailPage", () => {
  it("shows a configuration notice when NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN is unset", async () => {
    getPublicBffOrigin.mockReturnValue(undefined);
    getServerSession.mockResolvedValue(null);

    await renderCampaignDetailPage();

    expect(screen.getByText("Não configurado")).toBeInTheDocument();
  });

  it("shows a login link when there is no session", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(null);

    await renderCampaignDetailPage();

    const link = screen.getByRole("link", { name: "Entrar" });
    expect(link).toHaveAttribute(
      "href",
      "https://bff.example/auth/login?redirect_after_login=%2Fcampaigns%2Fcamp-1",
    );
  });

  it("shows an error state when the campaign, plan, or approvals cannot be loaded", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerCampaign.mockResolvedValue(null);
    getServerPlan.mockResolvedValue(NO_PLAN);
    getServerApprovals.mockResolvedValue([]);

    await renderCampaignDetailPage();

    expect(screen.getByText("Não foi possível carregar a campanha")).toBeInTheDocument();
  });

  it("renders the brief, plan panel, and validation panel with no pending approval for this campaign", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerCampaign.mockResolvedValue(CAMPAIGN);
    getServerPlan.mockResolvedValue(NO_PLAN);
    getServerApprovals.mockResolvedValue([PENDING_APPROVAL_ELSEWHERE]);

    await renderCampaignDetailPage();

    expect(screen.getByText("Gerar leads qualificados")).toBeInTheDocument();
    expect(screen.getByText("Nenhuma estratégia gerada ainda para esta campanha.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Validar" })).toBeInTheDocument();
  });

  it("passes hasPendingApproval=true through to ValidationPanel when this campaign has a PENDING approval", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerCampaign.mockResolvedValue(CAMPAIGN);
    getServerPlan.mockResolvedValue(NO_PLAN);
    getServerApprovals.mockResolvedValue([PENDING_APPROVAL_THIS_CAMPAIGN]);

    await renderCampaignDetailPage();

    // ValidationPanel only shows the "already requested" note AFTER a successful Validar
    // click that returns requires_human_approval -- this test asserts the page renders
    // without error with a same-campaign PENDING approval present; the note's exact wiring
    // is unit-tested directly in tests/validation-panel.test.tsx.
    expect(screen.getByRole("button", { name: "Validar" })).toBeInTheDocument();
  });
});
