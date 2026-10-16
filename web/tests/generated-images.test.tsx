import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GeneratedImagesPanel } from "@/components/GeneratedImagesPanel";
import { setCsrfToken } from "@/lib/api/client";

const reply = (data: unknown) => Promise.resolve(new Response(JSON.stringify(data),
  { status: 200, headers: { "content-type": "application/json" } }));
afterEach(() => { vi.restoreAllMocks(); setCsrfToken(null); });

describe("GeneratedImagesPanel", () => {
  it("shows persisted private states without enabling image generation or exposing object path", async () => {
    const calls: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((url, options) => {
      calls.push(String(url));
      expect(options?.method).toBe("GET");
      return String(url).endsWith("/quote")
        ? reply({ mode: "COMMERCIAL", action: "image", credits: 15, extra_amount: "0.00" })
        : reply({ items: [{ id: "c-1", campaign_id: "c", campaign_version: 1,
                 state: "STORAGE_PENDING", width: 512, height: 512,
                 revision: 2, content_type: "image/png", available: false }],
                 has_more: false, generation_enabled: false });
    });
    render(<GeneratedImagesPanel campaignId="c" planVersion={1} />);
    await screen.findByText(/STORAGE_PENDING/);
    expect(screen.getByText(/Créditos previstos por imagem: 15/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Revisar créditos para gerar imagem" })).toBeDisabled();
    expect(screen.queryByText(/storage.googleapis.com/)).not.toBeInTheDocument();
    expect(calls).toHaveLength(2);
  });
  it("requires credit review and explicit confirmation before POST", async () => {
    const user = userEvent.setup();
    const posts: string[] = [];
    setCsrfToken("valid-test-csrf");
    vi.spyOn(globalThis, "fetch").mockImplementation((url, options) => {
      if (options?.method === "POST") {
        posts.push(String(url));
        return reply({ id: "creative-1", state: "STORED", available: true });
      }
      if (String(url).endsWith("/quote"))
        return reply({ mode: "COMMERCIAL", action: "image", credits: 15,
                       extra_amount: "0.00", cycle_id: "cycle", policy_version: "v1",
                       generation_enabled: true });
      return reply({ items: [], has_more: false, generation_enabled: true });
    });
    render(<GeneratedImagesPanel campaignId="campaign" planVersion={2} />);
    const prompt = await screen.findByLabelText("Descrição da imagem");
    await user.type(prompt, "Criativo premium de campanha");
    await user.click(screen.getByRole("button", { name: "Revisar créditos para gerar imagem" }));
    expect(posts).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Confirmar geração" }));
    await screen.findByText(/Criativo armazenado/);
    expect(posts).toHaveLength(1);
  });

});
