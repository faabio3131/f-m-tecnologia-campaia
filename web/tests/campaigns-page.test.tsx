import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import CampaignsPage from "@/app/(app)/(authenticated)/campaigns/page";
import { setCsrfToken } from "@/lib/api/client";

const auth = vi.hoisted(() => ({ tenant: "a", create: true }));
vi.mock("@/providers/AuthProvider", () => ({ useAuth: () => ({
  session: { tenant_id: auth.tenant, user_id: "owner" },
  me: { business_unit_id: "bu-1", permissions: auth.create ? ["CAMPAIGN_CREATE"] : [] },
}) }));

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

describe("CampaignsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks(); auth.tenant = "a"; auth.create = true;
    setCsrfToken("csrf-test-token");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    setCsrfToken(null);
  });

  it("mostra estado vazio e cria uma campanha via briefing", async () => {
    let briefBody: unknown = null;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/briefs") && init?.method === "POST") {
        briefBody = JSON.parse(String(init.body));
        return jsonResponse(202, {
          id: "camp-1",
          name: "",
          objective: (briefBody as { objective: string }).objective,
          state: "DRAFT",
        });
      }
      if (url.endsWith("/campaigns")) return jsonResponse(200, { items: [] });
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<CampaignsPage />);

    await waitFor(() => expect(screen.getByText("Nenhuma campanha ainda")).toBeInTheDocument());

    await user.type(screen.getByLabelText("Objetivo"), "Gerar leads qualificados");
    await user.click(screen.getByRole("button", { name: /enviar briefing/i }));

    await waitFor(() => expect(screen.getByText("Gerar leads qualificados")).toBeInTheDocument());
    expect(briefBody).toMatchObject({ objective: "Gerar leads qualificados" });
  });
  it("does not expose briefing writes to a viewer", async () => {
    auth.create = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse(200, { items: [] }));
    render(<CampaignsPage />);
    await screen.findByText("Nenhuma campanha ainda");
    expect(screen.queryByLabelText("Objetivo")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enviar briefing" })).not.toBeInTheDocument();
  });

  it("explicit brand selection sends the displayed version and selected asset IDs", async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    vi.spyOn(globalThis, "fetch").mockImplementation((input, options) => {
      const url = String(input);
      if (url.endsWith("/brand-profiles")) return jsonResponse(200, [{ id: "bp-1", name: "Marca", tone: "claro", version: 2 }]);
      if (url.endsWith("/brand-profiles/bp-1/assets")) return jsonResponse(200, {
        items: [{ id: "asset-1", kind: "LOGO", status: "READY", width: 2, height: 3, content_url: null }],
        next_cursor: null, capability: { enabled: true },
      });
      if (url.endsWith("/briefs")) { body = JSON.parse(String(options?.body)); return jsonResponse(202, { id: "camp-new", objective: "Campanha selecionada", state: "DRAFT" }); }
      return jsonResponse(200, { items: [] });
    });
    render(<CampaignsPage />);
    await screen.findByText("Sem Brand Kit selecionado.");
    await user.click(screen.getByRole("button", { name: "Escolher Brand Kit" }));
    const selector = await screen.findByLabelText("Brand Kit da campanha");
    await screen.findByRole("option", { name: "Marca · versão 2" });
    expect(selector).toHaveValue("");
    await user.selectOptions(selector, "bp-1");
    await user.click(await screen.findByRole("checkbox"));
    await user.type(screen.getByLabelText("Objetivo"), "Campanha selecionada");
    await user.click(screen.getByRole("button", { name: "Enviar briefing" }));
    await screen.findByText("Campanha selecionada");
    expect(body.brand_selection).toEqual({ brand_profile_id: "bp-1", expected_version: 2, asset_ids: ["asset-1"] });
  });

  it("uncertain submission keeps body and nonce until confirmed", async () => {
    const user = userEvent.setup();
    const calls: RequestInit[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((url, options) => {
      if (String(url).endsWith("/briefs")) {
        calls.push(options!);
        if (calls.length === 1) return Promise.reject(new TypeError("response lost"));
        return jsonResponse(202, { id: "camp-new", objective: "Estável", state: "DRAFT" });
      }
      return jsonResponse(200, { items: [] });
    });
    render(<CampaignsPage />);
    await user.type(screen.getByLabelText("Objetivo"), "Estável");
    await user.click(screen.getByRole("button", { name: "Enviar briefing" }));
    await screen.findByRole("button", { name: "Conferir envio do briefing" });
    expect(screen.getByLabelText("Objetivo")).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Conferir envio do briefing" }));
    await screen.findByText("Estável");
    expect(calls).toHaveLength(2);
    expect(calls[0].body).toBe(calls[1].body);
    expect(new Headers(calls[0].headers).get("idempotency-key")).toBe(new Headers(calls[1].headers).get("idempotency-key"));
  });

  it("tenant switch clears the previous campaign list immediately", async () => {
    let count = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse(200, { items: ++count === 1
      ? [{ id: "camp-a", name: "Campanha privada A", state: "DRAFT" }] : [] }));
    const view = render(<CampaignsPage />);
    await screen.findByText("Campanha privada A");
    auth.tenant = "b"; view.rerender(<CampaignsPage />);
    expect(screen.queryByText("Campanha privada A")).not.toBeInTheDocument();
    await screen.findByText("Nenhuma campanha ainda");
  });

});
