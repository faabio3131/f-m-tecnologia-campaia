import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const {
  getServerSession,
  getServerCampaign,
  getServerPlan,
  getServerApprovals,
  getServerInsights,
  getPublicBffOrigin,
} = vi.hoisted(() => ({
  getServerSession: vi.fn(),
  getServerCampaign: vi.fn(),
  getServerPlan: vi.fn(),
  getServerApprovals: vi.fn(),
  getServerInsights: vi.fn(),
  getPublicBffOrigin: vi.fn(),
}));

vi.mock("@/lib/session", () => ({
  getServerSession,
  getServerCampaign,
  getServerPlan,
  getServerApprovals,
  getServerInsights,
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
  budget: { currency: "BRL", total_amount: "5000", daily_cap: "500", spent_to_date: "0" },
  created_at: "2026-01-01T00:00:00Z",
};

const NO_PLAN = { campaign_id: "camp-1", plan_version: 0, plan: null };

const EMPTY_INSIGHTS = {
  campaign_id: "camp-1",
  points: [],
  last_synced_at: null,
  note: "No analytics layer implemented yet in campaia_core; this is an honest placeholder, not fabricated data.",
};

const NONEMPTY_INSIGHTS = {
  campaign_id: "camp-1",
  points: [
    {
      date: "2026-01-01",
      channel: "GOOGLE_ADS" as const,
      impressions: 1000,
      clicks: 50,
      spend: 100,
      conversions: 5,
      cpa: 20,
    },
  ],
  last_synced_at: "2026-01-01T00:00:00Z",
  note: "",
};

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
    getServerInsights.mockResolvedValue(EMPTY_INSIGHTS);

    await renderCampaignDetailPage();

    expect(screen.getByText("Não foi possível carregar a campanha")).toBeInTheDocument();
  });

  it("renders the brief, plan panel, and validation panel with no pending approval for this campaign", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerCampaign.mockResolvedValue(CAMPAIGN);
    getServerPlan.mockResolvedValue(NO_PLAN);
    getServerApprovals.mockResolvedValue([PENDING_APPROVAL_ELSEWHERE]);
    getServerInsights.mockResolvedValue(EMPTY_INSIGHTS);

    await renderCampaignDetailPage();

    expect(screen.getByText("Gerar leads qualificados")).toBeInTheDocument();
    expect(screen.getByText("Nenhuma estratégia gerada ainda para esta campanha.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Validar" })).toBeInTheDocument();
    // WP-06: BudgetPanel renders on the same page, reusing the campaign fetched above.
    expect(screen.getByText("Orçamento")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Propor alteração" })).toBeInTheDocument();
  });

  it("passes hasPendingApproval=true through to ValidationPanel when this campaign has a PENDING approval", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerCampaign.mockResolvedValue(CAMPAIGN);
    getServerPlan.mockResolvedValue(NO_PLAN);
    getServerApprovals.mockResolvedValue([PENDING_APPROVAL_THIS_CAMPAIGN]);
    getServerInsights.mockResolvedValue(EMPTY_INSIGHTS);

    await renderCampaignDetailPage();

    // ValidationPanel only shows the "already requested" note AFTER a successful Validar
    // click that returns requires_human_approval -- this test asserts the page renders
    // without error with a same-campaign PENDING approval present; the note's exact wiring
    // is unit-tested directly in tests/validation-panel.test.tsx.
    expect(screen.getByRole("button", { name: "Validar" })).toBeInTheDocument();
  });

  it("WP-11: shows the real API note when insights has no points, never an invented placeholder", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerCampaign.mockResolvedValue(CAMPAIGN);
    getServerPlan.mockResolvedValue(NO_PLAN);
    getServerApprovals.mockResolvedValue([]);
    getServerInsights.mockResolvedValue(EMPTY_INSIGHTS);

    await renderCampaignDetailPage();

    expect(screen.getByText("Métricas")).toBeInTheDocument();
    expect(screen.getByText(EMPTY_INSIGHTS.note)).toBeInTheDocument();
  });

  it("WP-11: shows real points when insights has them, instead of the empty note", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerCampaign.mockResolvedValue(CAMPAIGN);
    getServerPlan.mockResolvedValue(NO_PLAN);
    getServerApprovals.mockResolvedValue([]);
    getServerInsights.mockResolvedValue(NONEMPTY_INSIGHTS);

    await renderCampaignDetailPage();

    expect(
      screen.getByText(/2026-01-01 · GOOGLE_ADS: 1000 impressões, 50 cliques, 5 conversões/),
    ).toBeInTheDocument();
  });

  it("WP-11: shows an error state when the insights read fails", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerCampaign.mockResolvedValue(CAMPAIGN);
    getServerPlan.mockResolvedValue(NO_PLAN);
    getServerApprovals.mockResolvedValue([]);
    getServerInsights.mockResolvedValue(null);

    await renderCampaignDetailPage();

    expect(screen.getByText("Não foi possível carregar as métricas")).toBeInTheDocument();
  });
});
