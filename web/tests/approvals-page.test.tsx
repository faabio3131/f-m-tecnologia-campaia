import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ApprovalsPage from "@/app/(app)/(authenticated)/approvals/page";
import { setCsrfToken } from "@/lib/api/client";

const auth = vi.hoisted(() => ({ tenant: "tenant-a", user: "reviewer", unit: "bu-1", permissions: ["APPROVAL_DECIDE"] }));
const step = vi.hoisted(() => ({ ready: true, testMode: true, stepUpMessage: null,
  headers: vi.fn(() => ({ "x-step-up-token": "verified-hook-fixture" })), onIdToken: vi.fn(),
  consumePresentedToken: vi.fn(), noteError: vi.fn() }));
vi.mock("@/providers/AuthProvider", () => ({ useAuth: () => ({
  session: { tenant_id: auth.tenant, user_id: auth.user }, me: { user_id: auth.user, business_unit_id: auth.unit, permissions: auth.permissions },
}) }));
vi.mock("@/hooks/useAdministrativeStepUp", () => ({ useAdministrativeStepUp: () => step }));

function response(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }));
}
const PENDING = { id: "appr-1", campaign_id: "camp-1", kind: "PUBLISH", reason: "", requested_by: "owner",
  plan_version: 1, status: "PENDING", requires_dual_approval: false, decided_by: [],
  created_at: "2026-10-16T00:00:00Z", expires_at: "2026-10-17T00:00:00Z", decision_reason: null };
const capability = { enabled: true, mode: "SIMULATED", can_generate: false, billing_required: false, max_variants: 5 };
const copy = { id: "copy-1", campaign_id: "camp-1", kind: "copy", version: 1, plan_version: 1, current: true,
  output: { variacoes: ["Texto para conferência"] }, request_summary: { channel: "GOOGLE_ADS" },
  provider: "SIM-CREATIVE-FIXTURE", model: "fixture", prompt_version: "v1", created_at: "2026-10-16T00:00:00Z" };
function materials(url: string, version = 1) {
  if (url.endsWith("/campaigns/camp-1")) return response({ id: "camp-1", brief: {} });
  if (url.endsWith("/plan")) return response({ campaign_id: "camp-1", plan_version: version, plan: { output: { objetivo: "Campanha" } } });
  if (url.endsWith("/proposals/copy")) return response({ items: [copy], next_cursor: null, capability });
  if (url.endsWith("/proposals/audience")) return response({ items: [], next_cursor: null, capability });
  throw new Error("Unexpected read: " + url);
}
beforeEach(() => {
  auth.tenant = "tenant-a"; auth.user = "reviewer"; auth.unit = "bu-1"; auth.permissions = ["APPROVAL_DECIDE"];
  step.ready = true; vi.clearAllMocks(); setCsrfToken("csrf-test-token");
});
afterEach(() => { vi.restoreAllMocks(); setCsrfToken(null); });
async function review(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByTestId("approve-appr-1");
  await user.click(screen.getByRole("button", { name: "Ver materiais para revisar" }));
  await screen.findByText("Texto para conferência");
  await waitFor(() => expect(screen.getByTestId("approve-appr-1")).toBeEnabled());
}
describe("ApprovalsPage", () => {
  it("shows an empty queue", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response([]));
    render(<ApprovalsPage />);
    await screen.findByText("Nenhuma aprovação pendente");
  });

  it("reviews the version and materials and uses the existing step-up hook for approval", async () => {
    const user = userEvent.setup(), writes: RequestInit[] = [];
    let saved = false;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, options) => {
      const url = String(input);
      if (options?.method === "POST") { writes.push(options); saved = true; return response({ ...PENDING, status: "APPROVED", decided_by: ["reviewer"] }); }
      if (url.endsWith("/approvals")) return response(saved ? [] : [PENDING]);
      return materials(url);
    });
    render(<ApprovalsPage />);
    await screen.findByTestId("approve-appr-1");
    expect(screen.getByTestId("approve-appr-1")).toBeDisabled();
    await review(user);
    expect(screen.getByRole("link", { name: "Abrir campanha" })).toHaveAttribute("href", "/campaigns/camp-1");
    await user.click(screen.getByTestId("approve-appr-1"));
    await screen.findByText("Nenhuma aprovação pendente");
    expect(JSON.parse(writes[0].body as string)).toEqual({ decision: "APPROVE" });
    expect(new Headers(writes[0].headers).get("x-step-up-token")).toBe("verified-hook-fixture");
    expect(step.consumePresentedToken).toHaveBeenCalledOnce();
  });

  it("displays the real separation-of-duties refusal", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation((input, options) => {
      if (options?.method === "POST") return response({ code: "SEPARATION_OF_DUTIES", message: "Quem propôs não pode aprovar." }, 403);
      if (String(input).endsWith("/approvals")) return response([PENDING]);
      return materials(String(input));
    });
    render(<ApprovalsPage />);
    await review(user); await user.click(screen.getByTestId("approve-appr-1"));
    await screen.findByText("Quem propôs não pode aprovar.");
    expect(screen.queryByRole("button", { name: "Conferir mesma decisão" })).not.toBeInTheDocument();
  });

  it("requests actionable changes with a preserved reason and escapes returned text", async () => {
    const user = userEvent.setup();
    let saved = false, body: unknown;
    const reason = "<script>não execute</script> Ajustar o convite.";
    vi.spyOn(globalThis, "fetch").mockImplementation((input, options) => {
      if (options?.method === "POST") {
        body = JSON.parse(options.body as string); saved = true;
        return response({ ...PENDING, status: "CHANGES_REQUESTED", decision_reason: reason });
      }
      if (String(input).endsWith("/approvals")) return response([saved ? { ...PENDING, status: "CHANGES_REQUESTED", decision_reason: reason } : PENDING]);
      return materials(String(input));
    });
    const view = render(<ApprovalsPage />);
    await screen.findByTestId("changes-appr-1");
    await user.click(screen.getByTestId("changes-appr-1"));
    await screen.findByText("Descreva o ajuste solicitado antes de enviar.");
    expect(body).toBeUndefined();
    await user.type(screen.getByLabelText("Motivo da decisão para appr-1"), reason);
    await user.click(screen.getByTestId("changes-appr-1"));
    await screen.findByText("Motivo da decisão: " + reason);
    expect(body).toEqual({ decision: "REQUEST_CHANGES", reason });
    expect(view.container.querySelector("script")).toBeNull();
  });

  it("keeps the exact decision and reason through an unknown response and rate-limited retry", async () => {
    const user = userEvent.setup(), writes: RequestInit[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, options) => {
      if (options?.method === "POST") {
        writes.push(options);
        if (writes.length === 1) return Promise.reject(new TypeError("lost"));
        if (writes.length === 2) return response({ code: "RATE_LIMITED", message: "Aguarde" }, 429);
        return response({ ...PENDING, status: "CHANGES_REQUESTED", decision_reason: "Ajuste o convite." });
      }
      if (String(input).endsWith("/approvals")) return response([PENDING]);
      return materials(String(input));
    });
    render(<ApprovalsPage />);
    await screen.findByTestId("changes-appr-1");
    await user.type(screen.getByLabelText("Motivo da decisão para appr-1"), "Ajuste o convite.");
    await user.click(screen.getByTestId("changes-appr-1"));
    await screen.findByRole("button", { name: "Conferir mesma decisão" });
    expect(screen.getByLabelText("Motivo da decisão para appr-1")).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Conferir mesma decisão" }));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(screen.getByTestId("reject-appr-1")).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Conferir mesma decisão" }));
    await waitFor(() => expect(writes).toHaveLength(3));
    for (const write of writes.slice(1)) {
      expect(write.body).toBe(writes[0].body);
      expect(new Headers(write.headers).get("idempotency-key")).toBe(new Headers(writes[0].headers).get("idempotency-key"));
    }
  });

  it("cannot approve materials from another plan version", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(input =>
      String(input).endsWith("/approvals") ? response([PENDING]) : materials(String(input), 2));
    render(<ApprovalsPage />);
    await screen.findByRole("button", { name: "Ver materiais para revisar" });
    await user.click(screen.getByRole("button", { name: "Ver materiais para revisar" }));
    await screen.findByText(/A campanha mudou. Este pedido/);
    expect(screen.getByTestId("approve-appr-1")).toBeDisabled();
    expect(screen.getByTestId("reject-appr-1")).toBeEnabled();
  });

  it("read-only access and the proposer expose no eligible decision", async () => {
    auth.permissions = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response([PENDING]));
    const view = render(<ApprovalsPage />);
    await screen.findByTestId("approval-appr-1");
    expect(screen.queryByTestId("approve-appr-1")).not.toBeInTheDocument();
    auth.permissions = ["APPROVAL_DECIDE"]; auth.user = "owner";
    view.rerender(<ApprovalsPage />);
    await screen.findByTestId("approve-appr-1");
    expect(screen.getByTestId("changes-appr-1")).toBeDisabled();
    expect(screen.getByText("Quem propôs não pode decidir este pedido.")).toBeVisible();
  });

  it("requires step-up before a new sensitive decision", async () => {
    step.ready = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response([PENDING]));
    const view = render(<ApprovalsPage />);
    await screen.findByTestId("changes-appr-1");
    expect(screen.getByTestId("changes-appr-1")).toBeDisabled();
    step.ready = true;
    view.rerender(<ApprovalsPage />);
    expect(screen.getByTestId("changes-appr-1")).toBeEnabled();
  });

  it("a confirmed vote remains confirmed if reloading the queue fails", async () => {
    const user = userEvent.setup();
    let saved = false;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, options) => {
      if (options?.method === "POST") { saved = true; return response({ ...PENDING, status: "REJECTED", decision_reason: "Refazer." }); }
      if (String(input).endsWith("/approvals")) return saved ? Promise.reject(new Error("read failed")) : response([PENDING]);
      return materials(String(input));
    });
    render(<ApprovalsPage />);
    await screen.findByTestId("reject-appr-1");
    await user.click(screen.getByTestId("reject-appr-1"));
    await screen.findByText("Decisão registrada. Não foi possível atualizar a fila; recarregue para conferir.");
    expect(screen.queryByRole("button", { name: "Conferir mesma decisão" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("approve-appr-1")).not.toBeInTheDocument();
  });

  it("a late queue response cannot reveal data after tenant switch", async () => {
    let finish: ((value: Response) => void) | undefined;
    const pending = new Promise<Response>(resolve => { finish = resolve; });
    vi.spyOn(globalThis, "fetch").mockImplementation(() => auth.tenant === "tenant-a" ? pending : response([]));
    const view = render(<ApprovalsPage />);
    auth.tenant = "tenant-b";
    view.rerender(<ApprovalsPage />);
    await screen.findByText("Nenhuma aprovação pendente");
    await act(async () => {
      finish!(new Response(JSON.stringify([{ ...PENDING, decision_reason: "private-tenant-a" }]), { status: 200, headers: { "content-type": "application/json" } }));
    });
    await waitFor(() => expect(screen.queryByText(/private-tenant-a/)).not.toBeInTheDocument());
    expect(within(view.container).queryByTestId("approval-appr-1")).not.toBeInTheDocument();
  });
});
