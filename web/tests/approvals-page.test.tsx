import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ApprovalsPage from "@/app/(app)/(authenticated)/approvals/page";
import { setCsrfToken } from "@/lib/api/client";

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

const PENDING_APPROVAL = {
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
};

describe("ApprovalsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setCsrfToken("csrf-test-token");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    setCsrfToken(null);
  });

  it("mostra estado vazio quando nao ha aprovacoes pendentes", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/approvals")) return jsonResponse(200, []);
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(<ApprovalsPage />);

    await waitFor(() =>
      expect(screen.getByText("Nenhuma aprovação pendente")).toBeInTheDocument(),
    );
  });

  it("aprova uma solicitacao pendente e recarrega a lista", async () => {
    let approvalsCallCount = 0;
    let decisionBody: unknown = null;

    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/decision") && init?.method === "POST") {
        decisionBody = JSON.parse(String(init.body));
        return jsonResponse(200, { ...PENDING_APPROVAL, status: "APPROVED" });
      }
      if (url.endsWith("/approvals")) {
        approvalsCallCount += 1;
        return jsonResponse(200, approvalsCallCount === 1 ? [PENDING_APPROVAL] : []);
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<ApprovalsPage />);

    await waitFor(() => expect(screen.getByTestId("approve-appr-1")).toBeInTheDocument());
    await user.click(screen.getByTestId("approve-appr-1"));

    await waitFor(() => expect(decisionBody).toMatchObject({ decision: "APPROVE" }));
    await waitFor(() =>
      expect(screen.getByText("Nenhuma aprovação pendente")).toBeInTheDocument(),
    );
  });

  it("mostra o erro real de segregacao de funcoes quando o backend recusa", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/decision") && init?.method === "POST") {
        return jsonResponse(403, {
          code: "SEPARATION_OF_DUTIES",
          message: "Quem propos a acao nao pode aprova-la.",
        });
      }
      if (url.endsWith("/approvals")) return jsonResponse(200, [PENDING_APPROVAL]);
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<ApprovalsPage />);

    await waitFor(() => expect(screen.getByTestId("approve-appr-1")).toBeInTheDocument());
    await user.click(screen.getByTestId("approve-appr-1"));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByText(/nao pode aprova-la/i)).toBeInTheDocument();
  });
});
