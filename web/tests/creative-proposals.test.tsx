import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CreativeProposalsPanel } from "@/components/CreativeProposalsPanel";
import { setCsrfToken } from "@/lib/api/client";
function response(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }));
}
const capability = { enabled: true, mode: "SIMULATED", max_variants: 5, billing_required: false, can_generate: true };
const output = { id: "p-1", campaign_id: "c-1", kind: "copy", version: 1, plan_version: 2, current: true,
  output: { variacoes: ["Texto seguro", "Outra opção"] }, request_summary: { channel: "GOOGLE_ADS" },
  provider: "SIM-CREATIVE-FIXTURE", model: "fixture", prompt_version: "copy-v1", created_at: "2026-10-16T00:00:00Z" };
const quote = { mode: "COMMERCIAL", action: "copy", cycle_id: "cycle-1", policy_version: "v1", credits: 3,
  extra_amount: "0.00", included_available: 30, kind: "copy", max_variants: 5 };
const props = { campaignId: "c-1", planVersion: 1, channels: ["GOOGLE_ADS"], product: "Oferta",
  audience: "Adultos", busy: false, onBusy: vi.fn(), onDelivered: vi.fn().mockResolvedValue(undefined) };
beforeEach(() => setCsrfToken("csrf-proposal-test"));
afterEach(() => { vi.restoreAllMocks(); setCsrfToken(null); });
async function prepare(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByText("Ambiente de teste: geração simulada.");
  await user.type(screen.getByLabelText("Tom dos textos"), "direto");
  await user.click(screen.getByRole("button", { name: "Gerar proposta" }));
}
describe("CreativeProposalsPanel", () => {
  it("a terminal no-delivery result unlocks a previously uncertain proposal", async () => {
    const user = userEvent.setup();
    let posts = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((url, options) => {
      if (String(url).endsWith("/quote")) return response(quote);
      if (options?.method === "POST") {
        posts++;
        if (posts === 1) return Promise.reject(new TypeError("lost"));
        return response({ code: "AI_OPERATION_FAILED", message: "Operação encerrada sem débito" }, 422);
      }
      return response({ items: [], next_cursor: null, capability });
    });
    render(<CreativeProposalsPanel {...props} />);
    await prepare(user); await user.click(screen.getByRole("button", { name: "Confirmar proposta" }));
    await screen.findByRole("button", { name: "Conferir mesma proposta" });
    await user.click(screen.getByRole("button", { name: "Conferir mesma proposta" }));
    await screen.findByText("Operação encerrada sem débito");
    expect(screen.getByLabelText("Oferta dos textos")).toBeEnabled();
    expect(posts).toBe(2);
  });

  it("refreshes current-context markers after the strategy version changes", async () => {
    let stale = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(url => response({
      items: String(url).endsWith("copy") ? [{ ...output, current: !stale }] : [],
      next_cursor: null, capability,
    }));
    const view = render(<CreativeProposalsPanel {...props} />);
    await screen.findByText(/Contexto vigente/);
    stale = true;
    view.rerender(<CreativeProposalsPanel {...props} planVersion={3} />);
    await screen.findByText(/Contexto anterior/);
    expect(screen.queryByText(/Contexto vigente/)).not.toBeInTheDocument();
  });

  it("reviews three credits before sending and displays preserved text and provenance", async () => {
    const user = userEvent.setup();
    let saved = false;
    const calls: RequestInit[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((url, options) => {
      if (String(url).endsWith("/quote")) return response(quote);
      if (options?.method === "POST") { calls.push(options); saved = true; return response(output, 201); }
      return response({ items: saved && String(url).endsWith("copy") ? [output] : [], next_cursor: null, capability });
    });
    render(<CreativeProposalsPanel {...props} />);
    await prepare(user);
    expect(calls).toHaveLength(0);
    expect(screen.getByText(/Esta entrega utiliza 3 créditos/)).toBeVisible();
    expect(screen.getByLabelText("Oferta dos textos")).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Confirmar proposta" }));
    await screen.findByText("Texto seguro");
    expect(calls).toHaveLength(1);
    expect(JSON.parse(calls[0].body as string)).toMatchObject({
      expected_plan_version: 1, channel: "GOOGLE_ADS", variants: 5, offer: "Oferta", tone: "direto",
      credit_confirmation: { credits: 3, cycle_id: "cycle-1" },
    });
    await user.click(screen.getByText("Contexto e origem"));
    expect(screen.getByText(/SIM-CREATIVE-FIXTURE · fixture/)).toBeVisible();
  });

  it("keeps exactly the same body and nonce after uncertainty, including a rate-limited retry", async () => {
    const user = userEvent.setup(), calls: RequestInit[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((url, options) => {
      if (String(url).endsWith("/quote")) return response(quote);
      if (options?.method === "POST") {
        calls.push(options);
        if (calls.length === 1) return Promise.reject(new TypeError("lost response"));
        if (calls.length === 2) return response({ code: "RATE_LIMITED", message: "Aguarde" }, 429);
        return response(output, 201);
      }
      return response({ items: [], next_cursor: null, capability });
    });
    render(<CreativeProposalsPanel {...props} />);
    await prepare(user);
    await user.click(screen.getByRole("button", { name: "Confirmar proposta" }));
    await screen.findByRole("button", { name: "Conferir mesma proposta" });
    expect(screen.getByLabelText("Tipo de proposta")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Voltar aos campos" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Conferir mesma proposta" }));
    await waitFor(() => expect(calls).toHaveLength(2));
    expect(screen.getByLabelText("Tom dos textos")).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Conferir mesma proposta" }));
    await screen.findByText("Textos entregues · versão 1.");
    expect(calls).toHaveLength(3);
    for (const call of calls.slice(1)) {
      expect(call.body).toBe(calls[0].body);
      expect(new Headers(call.headers).get("idempotency-key")).toBe(new Headers(calls[0].headers).get("idempotency-key"));
    }
  });

  it("a confirmed write stays confirmed when refreshing fails", async () => {
    const user = userEvent.setup();
    let saved = false;
    const delivered = vi.fn().mockRejectedValue(new Error("read failed"));
    vi.spyOn(globalThis, "fetch").mockImplementation((url, options) => {
      if (String(url).endsWith("/quote")) return response(quote);
      if (options?.method === "POST") { saved = true; return response(output, 201); }
      return response({ items: [], next_cursor: null, capability });
    });
    render(<CreativeProposalsPanel {...props} onDelivered={delivered} />);
    await prepare(user); await user.click(screen.getByRole("button", { name: "Confirmar proposta" }));
    await screen.findByText(/Entrega confirmada. Atualize/);
    expect(saved).toBe(true);
    expect(screen.queryByRole("button", { name: "Conferir mesma proposta" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Oferta dos textos")).toBeEnabled();
  });

  it("known rejection allows revision and obtains a fresh quote", async () => {
    const user = userEvent.setup(), calls: RequestInit[] = [];
    let quotes = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((url, options) => {
      if (String(url).endsWith("/quote")) { quotes++; return response(quote); }
      if (options?.method === "POST") { calls.push(options); return response({ code: "AI_INPUT_CHANGED", message: "Contexto mudou" }, 409); }
      return response({ items: [], next_cursor: null, capability });
    });
    render(<CreativeProposalsPanel {...props} />);
    await prepare(user); await user.click(screen.getByRole("button", { name: "Confirmar proposta" }));
    await screen.findByText("Contexto mudou");
    expect(screen.getByLabelText("Tom dos textos")).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Gerar proposta" }));
    expect(quotes).toBe(2); expect(calls).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Voltar aos campos" }));
    expect(screen.getByLabelText("Tipo de proposta")).toBeEnabled();
  });

  it("sends audience exclusions and explicit sensitivity with its two-credit confirmation", async () => {
    const user = userEvent.setup(), calls: RequestInit[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((url, options) => {
      if (String(url).endsWith("/quote")) return response({ ...quote, action: "audience", kind: "audience", credits: 2 });
      if (options?.method === "POST") { calls.push(options); return response({ ...output, kind: "audience", output: { segmentos: ["Adultos"], exclusoes: [], sensivel: true } }, 201); }
      return response({ items: [], next_cursor: null, capability });
    });
    render(<CreativeProposalsPanel {...props} />);
    await screen.findByText("Ambiente de teste: geração simulada.");
    await user.selectOptions(screen.getByLabelText("Tipo de proposta"), "audience");
    await user.type(screen.getByLabelText("Exclusões (uma por linha)"), "Menores\nOutro grupo");
    await user.click(screen.getByLabelText("Público envolve tema sensível"));
    await user.click(screen.getByRole("button", { name: "Gerar proposta" }));
    expect(screen.getByText(/Esta entrega utiliza 2 créditos/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Confirmar proposta" }));
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(JSON.parse(calls[0].body as string)).toMatchObject({
      audience: "Adultos", region: "BR", exclusions: ["Menores", "Outro grupo"], sensitive_declared: true,
    });
  });

  it("read-only capability preserves historical drafts without enabling generation", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(url => response({
      items: String(url).endsWith("copy") ? [{ ...output, current: false }] : [],
      next_cursor: null, capability: { ...capability, can_generate: false },
    }));
    render(<CreativeProposalsPanel {...props} />);
    await screen.findByText("Texto seguro");
    expect(screen.getByRole("button", { name: "Gerar proposta" })).toBeDisabled();
    expect(within(screen.getByRole("region", { name: "Histórico de Textos" })).getByText(/Contexto anterior/)).toBeVisible();
  });
});
