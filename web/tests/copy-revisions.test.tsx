import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CopyRevisionPanel } from "@/components/CopyRevisionPanel";
import type { CreativeProposal } from "@/contracts/types";
import { setCsrfToken } from "@/lib/api/client";
function response(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }));
}
const source: CreativeProposal = { id: "copy-1", campaign_id: "c-1", kind: "copy", version: 1, plan_version: 2, current: true,
  output: { variacoes: ["Texto original um", "Texto original dois"] }, request_summary: { channel: "GOOGLE_ADS" },
  provider: "fixture", model: "fixture", prompt_version: "v1", created_at: "2026-10-16T00:00:00Z" };
const quote = { mode: "COMMERCIAL", action: "revision", cycle_id: "cycle-1", policy_version: "v1",
  credits: 1, extra_amount: "0.00", included_available: 27, kind: "copy", max_variants: 1 };
function props() { return { campaignId: "c-1", source, planVersion: 2, busy: false, canGenerate: true,
  onBusy: vi.fn(), onDelivered: vi.fn().mockResolvedValue(undefined), onCancel: vi.fn() }; }
beforeEach(() => setCsrfToken("csrf-revision-test"));
afterEach(() => { vi.restoreAllMocks(); setCsrfToken(null); });
async function review(user: ReturnType<typeof userEvent.setup>) {
  await user.selectOptions(screen.getByLabelText("Texto para ajustar"), "1");
  await user.type(screen.getByLabelText("Instruções para o ajuste"), "Convite mais direto");
  await user.click(screen.getByRole("button", { name: "Revisar consumo do ajuste" }));
}
describe("CopyRevisionPanel", () => {
  it("shows the selected original and reviews one credit before replacing a single index", async () => {
    const user = userEvent.setup(), calls: RequestInit[] = [], current = props();
    vi.spyOn(globalThis, "fetch").mockImplementation((_url, options) => {
      if (options?.method === "POST") { calls.push(options); return response({ ...source, version: 2 }, 201); }
      return response(quote);
    });
    render(<CopyRevisionPanel {...current} />);
    await review(user);
    expect(screen.getByText("Texto original dois")).toBeVisible();
    expect(screen.getByText(/Este ajuste utiliza 1 crédito/)).toBeVisible();
    expect(calls).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Confirmar ajuste" }));
    await waitFor(() => expect(current.onDelivered).toHaveBeenCalledOnce());
    expect(JSON.parse(calls[0].body as string)).toEqual({
      expected_plan_version: 2, channel: "GOOGLE_ADS", variant_index: 1, instructions: "Convite mais direto",
      credit_confirmation: { cycle_id: "cycle-1", policy_version: "v1", credits: 1, extra_amount: "0.00" },
    });
    expect(current.onBusy).toHaveBeenLastCalledWith(false);
  });

  it("preserves exact body and nonce through uncertainty and a rejected recovery attempt", async () => {
    const user = userEvent.setup(), calls: RequestInit[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((_url, options) => {
      if (options?.method === "POST") {
        calls.push(options);
        if (calls.length === 1) return Promise.reject(new TypeError("lost"));
        if (calls.length === 2) return response({ code: "RATE_LIMITED", message: "Aguarde" }, 429);
        return response(source, 201);
      }
      return response(quote);
    });
    render(<CopyRevisionPanel {...props()} />);
    await review(user); await user.click(screen.getByRole("button", { name: "Confirmar ajuste" }));
    await screen.findByRole("button", { name: "Conferir mesmo ajuste" });
    expect(screen.getByLabelText("Texto para ajustar")).toBeDisabled();
    expect(screen.getByLabelText("Instruções para o ajuste")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Fechar ajuste" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Conferir mesmo ajuste" }));
    await waitFor(() => expect(calls).toHaveLength(2));
    expect(screen.getByLabelText("Texto para ajustar")).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Conferir mesmo ajuste" }));
    await waitFor(() => expect(calls).toHaveLength(3));
    for (const call of calls.slice(1)) {
      expect(call.body).toBe(calls[0].body);
      expect(new Headers(call.headers).get("idempotency-key")).toBe(new Headers(calls[0].headers).get("idempotency-key"));
    }
  });

  it("known invalid output allows editing with a fresh quote and intent", async () => {
    const user = userEvent.setup(), calls: RequestInit[] = [];
    let quoted = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((_url, options) => {
      if (options?.method === "POST") { calls.push(options); return response({ code: "AI_OUTPUT_UNCHANGED", message: "Texto não mudou" }, 422); }
      quoted++; return response(quote);
    });
    render(<CopyRevisionPanel {...props()} />);
    await review(user); await user.click(screen.getByRole("button", { name: "Confirmar ajuste" }));
    await screen.findByText("Texto não mudou");
    expect(screen.getByLabelText("Instruções para o ajuste")).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Revisar consumo do ajuste" }));
    await user.click(screen.getByRole("button", { name: "Confirmar ajuste" }));
    await waitFor(() => expect(calls).toHaveLength(2));
    expect(quoted).toBe(2);
    expect(new Headers(calls[0].headers).get("idempotency-key")).not.toBe(new Headers(calls[1].headers).get("idempotency-key"));
  });

  it("cancel before sending has no write and a confirmed delivery survives refresh failure", async () => {
    const user = userEvent.setup(), current = props();
    current.onDelivered.mockRejectedValue(new Error("read failed"));
    const calls: RequestInit[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((_url, options) => {
      if (options?.method === "POST") { calls.push(options); return response(source, 201); }
      return response(quote);
    });
    render(<CopyRevisionPanel {...current} />);
    await review(user);
    await user.click(screen.getByRole("button", { name: "Voltar aos ajustes" }));
    expect(calls).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Revisar consumo do ajuste" }));
    await user.click(screen.getByRole("button", { name: "Confirmar ajuste" }));
    await screen.findByText("Ajuste entregue. Atualize o histórico para conferir.");
    expect(screen.queryByRole("button", { name: "Conferir mesmo ajuste" })).not.toBeInTheDocument();
  });

  it("read-only access cannot prepare an adjustment", () => {
    render(<CopyRevisionPanel {...props()} canGenerate={false} />);
    expect(screen.getByLabelText("Instruções para o ajuste")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Revisar consumo do ajuste" })).toBeDisabled();
  });
});
