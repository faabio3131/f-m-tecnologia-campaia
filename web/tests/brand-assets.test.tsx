import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BrandAssetsPanel } from "@/components/BrandAssetsPanel";
import { setCsrfToken } from "@/lib/api/client";

function response(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }));
}
const asset = {
  id: "asset-1", brand_profile_id: "bp-1", kind: "LOGO", status: "READY", width: 2, height: 3,
  size_bytes: 80, content_type: "image/png", created_at: "2026-10-16T00:00:00Z",
  updated_at: "2026-10-16T00:00:00Z", content_url: "/api/campaia/brand-profiles/bp-1/assets/asset-1/content",
};
const capability = { enabled: true, mode: "SIMULATOR", max_input_bytes: 5242880, max_active_bytes: 5242880, used_bytes: 0 };
beforeEach(() => setCsrfToken("csrf-test-token"));
afterEach(() => { vi.restoreAllMocks(); setCsrfToken(null); });

describe("BrandAssetsPanel", () => {
  it("disabled capability and viewer expose no upload controls", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({
      items: [], next_cursor: null, capability: { ...capability, enabled: false, mode: "DISABLED" },
    }));
    render(<BrandAssetsPanel identity="bp-1" name="Marca" canManage={false} />);
    await screen.findByText("Os arquivos da marca estão indisponíveis no momento.");
    expect(screen.queryByLabelText("Imagem da marca")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enviar imagem" })).not.toBeInTheDocument();
  });

  it("uploads binary bytes and displays a confirmed private image", async () => {
    const user = userEvent.setup();
    let uploaded = false;
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((_url, options) => {
      if (options?.method === "POST") { uploaded = true; return response(asset, 201); }
      return response({ items: uploaded ? [asset] : [], next_cursor: null, capability });
    });
    render(<BrandAssetsPanel identity="bp-1" name="Marca" canManage />);
    const input = await screen.findByLabelText("Imagem da marca");
    const file = new File(["fixture bytes"], "logo.png", { type: "image/png" });
    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: "Enviar imagem" }));
    expect(await screen.findByRole("img", { name: "Logo de Marca" })).toHaveAttribute("src", asset.content_url);
    const call = fetchSpy.mock.calls.find(([, options]) => options?.method === "POST")!;
    expect(call[1]?.body).toBe(file);
    expect(new Headers(call[1]?.headers).get("idempotency-key")).toBeTruthy();
  });

  it("uncertain transport locks the same file and reuses its nonce", async () => {
    const user = userEvent.setup();
    const calls: RequestInit[] = [];
    let uploaded = false;
    vi.spyOn(globalThis, "fetch").mockImplementation((_url, options) => {
      if (options?.method === "POST") {
        calls.push(options);
        if (calls.length === 1) return Promise.reject(new TypeError("response lost"));
        uploaded = true; return response(asset, 201);
      }
      return response({ items: uploaded ? [asset] : [], next_cursor: null, capability });
    });
    render(<BrandAssetsPanel identity="bp-1" name="Marca" canManage />);
    const input = await screen.findByLabelText("Imagem da marca");
    await user.upload(input, new File(["fixture"], "logo.png", { type: "image/png" }));
    await user.click(screen.getByRole("button", { name: "Enviar imagem" }));
    await screen.findByRole("button", { name: "Conferir envio" });
    expect(input).toBeDisabled();
    expect(screen.getByLabelText("Finalidade da imagem")).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Conferir envio" }));
    await screen.findByText("Imagem salva.");
    expect(calls).toHaveLength(2);
    expect(calls[0].body).toBe(calls[1].body);
    expect(new Headers(calls[0].headers).get("idempotency-key")).toBe(new Headers(calls[1].headers).get("idempotency-key"));
    expect(input).not.toBeDisabled();
  });

  it("pending upload is not rendered as an image and recovery is explicit", async () => {
    const user = userEvent.setup();
    const pending = { ...asset, status: "UPLOAD_UNCERTAIN", content_url: null };
    let ready = false;
    vi.spyOn(globalThis, "fetch").mockImplementation((_url, options) => {
      if (options?.method === "POST") { ready = true; return response(asset); }
      return response({ items: [ready ? asset : pending], next_cursor: null, capability });
    });
    render(<BrandAssetsPanel identity="bp-1" name="Marca" canManage />);
    await screen.findByText(/Envio aguardando confirmação/);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Conferir arquivo" }));
    await screen.findByRole("img", { name: "Logo de Marca" });
  });

  it("delete requires explicit confirmation and then removes preview", async () => {
    const user = userEvent.setup();
    let deleted = false;
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((_url, options) => {
      if (options?.method === "DELETE") { deleted = true; return response({ ...asset, status: "DELETED", content_url: null }); }
      return response({ items: deleted ? [] : [asset], next_cursor: null, capability });
    });
    render(<BrandAssetsPanel identity="bp-1" name="Marca" canManage />);
    await screen.findByRole("img", { name: "Logo de Marca" });
    await user.click(screen.getByRole("button", { name: "Remover imagem" }));
    expect(fetchSpy.mock.calls.filter(([, options]) => options?.method === "DELETE")).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Confirmar remoção" }));
    await screen.findByText("Nenhum arquivo registrado.");
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("paginates without dropping newer assets", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(url => response(String(url).includes("?cursor=")
      ? { items: [{ ...asset, id: "asset-older", kind: "REFERENCE" }], next_cursor: null, capability }
      : { items: [asset], next_cursor: "asset-1", capability }));
    render(<BrandAssetsPanel identity="bp-1" name="Marca" canManage={false} />);
    await user.click(await screen.findByRole("button", { name: "Carregar arquivos anteriores" }));
    await waitFor(() => expect(screen.getAllByRole("img")).toHaveLength(2));
    expect(within(screen.getByTestId("brand-asset-asset-1")).getByText(/Disponível/)).toBeInTheDocument();
  });
});
