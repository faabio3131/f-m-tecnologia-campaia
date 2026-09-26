import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AuditPage from "@/app/(app)/(authenticated)/audit/page";
import { setCsrfToken } from "@/lib/api/client";

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

const EVENTS = [
  {
    id: "evt-1",
    occurred_at: "2026-09-26T10:00:00Z",
    actor_kind: "USER",
    actor_id: "user-1",
    action: "CAMPAIGN_CREATE",
    target: "camp-1",
    policy_decision_id: null,
    evidence: null,
  },
  {
    id: "evt-2",
    occurred_at: "2026-09-26T12:00:00Z",
    actor_kind: "SYSTEM",
    actor_id: null,
    action: "KILL_SWITCH",
    target: "TENANT",
    policy_decision_id: null,
    evidence: { scope: "TENANT", affected: [] },
  },
];

describe("AuditPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setCsrfToken("csrf-test-token");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    setCsrfToken(null);
  });

  it("mostra estado vazio quando não há eventos", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/audit-events")) return jsonResponse(200, { items: [], next_cursor: null });
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(<AuditPage />);

    await waitFor(() =>
      expect(screen.getByText(/nenhum evento de auditoria ainda/i)).toBeInTheDocument(),
    );
  });

  it("lista eventos reais, mais recente primeiro, mostrando evidência quando presente", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/audit-events")) return jsonResponse(200, { items: EVENTS, next_cursor: null });
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(<AuditPage />);

    await waitFor(() => expect(screen.getByText("KILL_SWITCH")).toBeInTheDocument());
    expect(screen.getByText("CAMPAIGN_CREATE")).toBeInTheDocument();

    // Mais recente (KILL_SWITCH, 12:00) aparece antes do mais antigo (CAMPAIGN_CREATE, 10:00).
    const actions = screen.getAllByText(/^(KILL_SWITCH|CAMPAIGN_CREATE)$/).map((el) => el.textContent);
    expect(actions).toEqual(["KILL_SWITCH", "CAMPAIGN_CREATE"]);

    // Evidencia real e mostrada (nunca escondida quando o backend a devolve).
    expect(screen.getByText(/"scope": "TENANT"/)).toBeInTheDocument();
  });

  it("carrega mais eventos via next_cursor real quando existe mais de uma página (achado 21)", async () => {
    const secondPageEvent = {
      id: "evt-3",
      occurred_at: "2026-09-26T08:00:00Z",
      actor_kind: "USER",
      actor_id: "user-2",
      action: "PLAN_REGENERATE",
      target: "camp-2",
      policy_decision_id: null,
      evidence: null,
    };
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("cursor=evt-1")) {
        return jsonResponse(200, { items: [secondPageEvent], next_cursor: null });
      }
      if (url.endsWith("/audit-events")) {
        return jsonResponse(200, { items: EVENTS, next_cursor: "evt-1" });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<AuditPage />);

    await waitFor(() => expect(screen.getByText("KILL_SWITCH")).toBeInTheDocument());
    const loadMoreButton = screen.getByRole("button", { name: /carregar mais/i });
    expect(loadMoreButton).toBeInTheDocument();

    await user.click(loadMoreButton);

    await waitFor(() => expect(screen.getByText("PLAN_REGENERATE")).toBeInTheDocument());
    // Ambas as páginas continuam visíveis -- carregar mais acrescenta, não substitui.
    expect(screen.getByText("KILL_SWITCH")).toBeInTheDocument();
    expect(screen.getByText("CAMPAIGN_CREATE")).toBeInTheDocument();
    // Sem next_cursor na segunda página, o botão desaparece.
    expect(screen.queryByRole("button", { name: /carregar mais/i })).not.toBeInTheDocument();
  });

  it("filtra por campaign_id via GET /audit-events?campaign_id=...", async () => {
    let lastUrl = "";
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      lastUrl = url;
      if (url.includes("/audit-events")) {
        const filtered = url.includes("campaign_id=camp-1") ? [EVENTS[0]] : EVENTS;
        return jsonResponse(200, { items: filtered, next_cursor: null });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<AuditPage />);

    await waitFor(() => expect(screen.getByText("KILL_SWITCH")).toBeInTheDocument());

    await user.type(screen.getByLabelText(/id da campanha/i), "camp-1");
    await user.click(screen.getByRole("button", { name: /^filtrar$/i }));

    await waitFor(() => expect(lastUrl).toContain("campaign_id=camp-1"));
    await waitFor(() => expect(screen.queryByText("KILL_SWITCH")).not.toBeInTheDocument());
    expect(screen.getByText("CAMPAIGN_CREATE")).toBeInTheDocument();
  });
});
