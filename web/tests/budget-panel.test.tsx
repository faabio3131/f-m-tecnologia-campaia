import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setCsrfToken } from "@/lib/api/client";
import { BudgetPanel } from "@/components/BudgetPanel";

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

// Reflete o formato REAL de resposta do backend: campos Decimal do pydantic v2
// serializam como string, nunca como number (achado da reconciliação, WP-06).
const BUDGET = { currency: "BRL", total_amount: "10000", daily_cap: "500", spent_to_date: "120.50" };

describe("BudgetPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setCsrfToken("csrf-test-token");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    setCsrfToken(null);
  });

  it("mostra o resumo do orçamento normalizando valores que chegam como string", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/approvals") && init?.method === "GET") {
        return jsonResponse(200, []);
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(<BudgetPanel campaignId="camp-1" budget={BUDGET} />);

    await waitFor(() => expect(screen.getByText("R$ 500,00")).toBeInTheDocument());
    expect(screen.getByText("R$ 10.000,00")).toBeInTheDocument();
    expect(screen.getByText("R$ 120,50")).toBeInTheDocument();
  });

  it("propõe uma mudança de orçamento via POST /approvals (BUDGET_CHANGE)", async () => {
    let created: Record<string, unknown> | null = null;

    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/approvals") && init?.method === "GET") {
        return jsonResponse(200, created ? [created] : []);
      }
      if (url.endsWith("/approvals") && init?.method === "POST") {
        created = {
          id: "appr-budget-1",
          campaign_id: "camp-1",
          kind: "BUDGET_CHANGE",
          requested_by: "user-1",
          amount: "600",
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
    render(<BudgetPanel campaignId="camp-1" budget={BUDGET} />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /propor mudança de orçamento/i })).toBeInTheDocument(),
    );
    await user.type(screen.getByLabelText(/novo orçamento diário/i), "600");
    await user.click(screen.getByRole("button", { name: /propor mudança de orçamento/i }));

    await waitFor(() => expect(created).not.toBeNull());
    await waitFor(() =>
      expect(screen.getByText(/pedido de mudança de orçamento pendente/i)).toBeInTheDocument(),
    );
  });

  it("aplica uma mudança já aprovada via PATCH /campaigns/{id}/budget, com step-up", async () => {
    const approved = {
      id: "appr-budget-2",
      campaign_id: "camp-1",
      kind: "BUDGET_CHANGE",
      requested_by: "user-1",
      amount: "700",
      status: "APPROVED",
      requires_dual_approval: false,
      decided_by: ["user-2"],
      created_at: "2026-09-26T00:00:00Z",
    };
    let patchedCount = 0;
    let stepUpHeaderValue: string | null = null;

    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/approvals") && init?.method === "GET") {
        return jsonResponse(200, [approved]);
      }
      if (url.endsWith("/campaigns/camp-1/budget") && init && init.method === "PATCH") {
        patchedCount += 1;
        stepUpHeaderValue = new Headers(init.headers).get("x-step-up-token");
        return jsonResponse(202, { id: "camp-1" });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<BudgetPanel campaignId="camp-1" budget={BUDGET} />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /aplicar alteração/i })).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /aplicar alteração/i }));

    await waitFor(() => expect(patchedCount).toBe(1));
    expect(stepUpHeaderValue).toBe("web-ui-confirmacao-explicita");
  });
});
