import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { getServerSession, getServerAuditEvents, getPublicBffOrigin } = vi.hoisted(() => ({
  getServerSession: vi.fn(),
  getServerAuditEvents: vi.fn(),
  getPublicBffOrigin: vi.fn(),
}));

vi.mock("@/lib/session", () => ({
  getServerSession,
  getServerAuditEvents,
  getPublicBffOrigin,
}));

async function renderAuditPage(searchParams: { campaign_id?: string } = {}) {
  const { default: AuditPage } = await import("@/app/audit/page");
  const element = await AuditPage({ searchParams: Promise.resolve(searchParams) });
  render(element);
}

const ME = {
  user_id: "user-admin-1",
  tenant_id: "demo-tenant",
  business_unit_id: "bu-1",
  roles: ["ADMIN"],
  permissions: ["AUDIT_VIEW"],
  mfa_enabled: true,
};

const EVENT = {
  id: "evt-1",
  occurred_at: "2026-01-01T12:00:00Z",
  actor_kind: "USER" as const,
  actor_id: "user-owner-1",
  action: "BUDGET_CHANGE",
  target: "camp-1",
  policy_decision_id: null,
  evidence: null,
};

const EVENT_2 = {
  ...EVENT,
  id: "evt-2",
  occurred_at: "2026-01-02T12:00:00Z",
  action: "KILL_SWITCH",
  target: "TENANT",
};

describe("AuditPage", () => {
  it("shows a configuration notice when NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN is unset", async () => {
    getPublicBffOrigin.mockReturnValue(undefined);
    getServerSession.mockResolvedValue(null);

    await renderAuditPage();

    expect(screen.getByText("Não configurado")).toBeInTheDocument();
  });

  it("shows a login link when there is no session", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(null);

    await renderAuditPage();

    const link = screen.getByRole("link", { name: "Entrar" });
    expect(link).toHaveAttribute(
      "href",
      "https://bff.example/auth/login?redirect_after_login=%2Faudit",
    );
    expect(getServerAuditEvents).not.toHaveBeenCalled();
  });

  it("shows an error state when the read fails (e.g. missing AUDIT_VIEW permission)", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerAuditEvents.mockResolvedValue(null);

    await renderAuditPage();

    expect(
      screen.getByText("Não foi possível carregar a trilha de auditoria"),
    ).toBeInTheDocument();
  });

  it("shows an empty note when there are no events", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerAuditEvents.mockResolvedValue([]);

    await renderAuditPage();

    expect(
      screen.getByText("Nenhum evento de auditoria registrado ainda."),
    ).toBeInTheDocument();
  });

  it("renders real events newest first", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerAuditEvents.mockResolvedValue([EVENT, EVENT_2]);

    await renderAuditPage();

    const rows = screen.getAllByRole("row").slice(1); // skip header row
    expect(rows[0]).toHaveTextContent("KILL_SWITCH");
    expect(rows[1]).toHaveTextContent("BUDGET_CHANGE");
    expect(screen.getAllByText(/USER — user-owner-1/)).toHaveLength(2);
  });

  it("passes campaign_id through to the read and shows the filter note", async () => {
    getPublicBffOrigin.mockReturnValue("https://bff.example");
    getServerSession.mockResolvedValue(ME);
    getServerAuditEvents.mockResolvedValue([EVENT]);

    await renderAuditPage({ campaign_id: "camp-1" });

    expect(getServerAuditEvents).toHaveBeenCalledWith("camp-1");
    expect(screen.getByText(/Filtrado pela campanha/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "ver todos os eventos" })).toHaveAttribute(
      "href",
      "/audit",
    );
  });
});
