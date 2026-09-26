import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setCsrfToken } from "@/lib/api/client";

vi.mock("next/navigation", () => ({
  useParams: () => ({ campaignId: "camp-1" }),
}));

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

const BASE_CAMPAIGN = {
  id: "camp-1",
  name: "",
  objective: "Gerar leads",
  state: "DRAFT",
  channels: [],
  external_resources: [],
  budget: { currency: "BRL", total_amount: 10000, daily_cap: 1000, spent_to_date: 0 },
  created_at: "2026-09-26T00:00:00Z",
};

describe("CampaignDetailPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setCsrfToken("csrf-test-token");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    setCsrfToken(null);
  });

  it("gera estratégia, valida e solicita aprovação quando aprovável", async () => {
    let planVersion = 0;
    let validateCalled = false;
    let approvalCreated = false;

    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/plan/regenerate") && init?.method === "POST") {
        planVersion = 1;
        return jsonResponse(202, {});
      }
      if (url.endsWith("/campaigns/camp-1/plan")) {
        return jsonResponse(200, {
          campaign_id: "camp-1",
          plan_version: planVersion,
          plan: planVersion > 0 ? { objetivo: "Gerar leads", funil: "TOPO_MEIO" } : null,
        });
      }
      if (url.endsWith("/validate") && init?.method === "POST") {
        validateCalled = true;
        return jsonResponse(200, {
          outcome: "APPROVABLE",
          requires_human_approval: true,
          requires_dual_approval: false,
          findings: [],
        });
      }
      if (url.endsWith("/campaigns/camp-1")) {
        return jsonResponse(200, BASE_CAMPAIGN);
      }
      if (url.endsWith("/approvals") && init?.method === "POST") {
        approvalCreated = true;
        return jsonResponse(201, {
          id: "appr-1",
          campaign_id: "camp-1",
          kind: "PUBLISH",
          reason: "",
          requested_by: "user-owner-1",
          plan_version: 1,
          status: "PENDING",
          requires_dual_approval: false,
          decided_by: [],
          created_at: "2026-09-26T00:00:00Z",
          expires_at: "2026-09-27T00:00:00Z",
        });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    const { default: CampaignDetailPage } = await import(
      "@/app/(app)/(authenticated)/campaigns/[campaignId]/page"
    );
    const user = userEvent.setup();
    render(<CampaignDetailPage />);

    await waitFor(() => expect(screen.getByText("Gerar leads")).toBeInTheDocument());
    expect(screen.getByText(/nenhuma estratégia gerada/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /gerar estratégia/i }));
    await waitFor(() => expect(screen.getByText(/topo_meio/i)).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /validar campanha/i }));
    await waitFor(() => expect(validateCalled).toBe(true));
    await waitFor(() => expect(screen.getByText(/resultado: approvable/i)).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /solicitar aprovação para publicar/i }));
    await waitFor(() => expect(approvalCreated).toBe(true));
    await waitFor(() => expect(screen.getByText(/pedido criado/i)).toBeInTheDocument());
  });
});
