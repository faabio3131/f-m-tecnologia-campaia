import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setCsrfToken } from "@/lib/api/client";
import { AutonomyPanel } from "@/components/AutonomyPanel";

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

// Reflete o formato REAL de GET /autonomy (backend/api/models.py::AutonomyResponse),
// incluindo `max_level_allowed`, campo aditivo ao contrato encontrado nesta reconciliação
// (WP-07) -- ver contracts/bff-openapi.yaml.
const SETTINGS = {
  level: 1,
  level_label: "APROVADO",
  max_level_allowed: 1,
  always_require_human: ["PUBLISH"],
  max_budget_change_pct: 20,
  updated_at: "2026-09-26T00:00:00Z",
};

describe("AutonomyPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setCsrfToken("csrf-test-token");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    setCsrfToken(null);
  });

  it("mostra o resumo do nível de autonomia vigente", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/autonomy") && init?.method === "GET") {
        return jsonResponse(200, SETTINGS);
      }
      if (url.endsWith("/approvals") && init?.method === "GET") {
        return jsonResponse(200, []);
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(<AutonomyPanel anchorCampaignId="camp-1" />);

    await waitFor(() => expect(screen.getByTestId("autonomy-level-label")).toHaveTextContent("APROVADO"));
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("PUBLISH", { exact: false })).toBeInTheDocument();
  });

  it("propõe uma mudança de nível via POST /approvals (AUTONOMY_CHANGE)", async () => {
    let created: Record<string, unknown> | null = null;

    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/autonomy") && init?.method === "GET") {
        return jsonResponse(200, SETTINGS);
      }
      if (url.endsWith("/approvals") && init?.method === "GET") {
        return jsonResponse(200, created ? [created] : []);
      }
      if (url.endsWith("/approvals") && init?.method === "POST") {
        created = {
          id: "appr-autonomy-1",
          campaign_id: "camp-1",
          kind: "AUTONOMY_CHANGE",
          requested_by: "user-1",
          amount: "1",
          status: "PENDING",
          requires_dual_approval: false,
          decided_by: [],
          created_at: "2026-09-26T00:00:00Z",
        };
        return jsonResponse(201, created);
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<AutonomyPanel anchorCampaignId="camp-1" />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /propor mudança de nível/i })).toBeInTheDocument(),
    );
    await user.type(screen.getByLabelText(/novo nível/i), "1");
    await user.click(screen.getByRole("button", { name: /propor mudança de nível/i }));

    await waitFor(() => expect(created).not.toBeNull());
    await waitFor(() =>
      expect(screen.getByText(/pedido de mudança de nível pendente/i)).toBeInTheDocument(),
    );
  });

  it("desabilita a proposta quando não há campanha âncora no tenant", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/autonomy") && init?.method === "GET") {
        return jsonResponse(200, SETTINGS);
      }
      if (url.endsWith("/approvals") && init?.method === "GET") {
        return jsonResponse(200, []);
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(<AutonomyPanel anchorCampaignId={null} />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /propor mudança de nível/i })).toBeDisabled(),
    );
    expect(
      screen.getByText(/é necessário existir ao menos uma campanha no tenant/i),
    ).toBeInTheDocument();
  });

  it("aplica uma mudança já aprovada via PUT /autonomy, com step-up, e recarrega o nível vigente", async () => {
    const approved = {
      id: "appr-autonomy-2",
      campaign_id: "camp-1",
      kind: "AUTONOMY_CHANGE",
      requested_by: "user-1",
      amount: "1",
      status: "APPROVED",
      requires_dual_approval: false,
      decided_by: ["user-2"],
      created_at: "2026-09-26T00:00:00Z",
    };
    let putCount = 0;
    let stepUpHeaderValue: string | null = null;
    let currentSettings = SETTINGS;

    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/autonomy") && init?.method === "GET") {
        return jsonResponse(200, currentSettings);
      }
      if (url.endsWith("/approvals") && init?.method === "GET") {
        return jsonResponse(200, [approved]);
      }
      if (url.endsWith("/autonomy") && init?.method === "PUT") {
        putCount += 1;
        stepUpHeaderValue = new Headers(init.headers).get("x-step-up-token");
        currentSettings = { ...SETTINGS, level: 1, level_label: "APROVADO" };
        return jsonResponse(200, currentSettings);
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<AutonomyPanel anchorCampaignId="camp-1" />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /aplicar nível de autonomia/i })).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /aplicar nível de autonomia/i }));

    await waitFor(() => expect(putCount).toBe(1));
    expect(stepUpHeaderValue).toBe("web-ui-confirmacao-explicita");
  });
});
