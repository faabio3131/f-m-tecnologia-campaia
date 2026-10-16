import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GeneratedImagesPanel } from "@/components/GeneratedImagesPanel";

const reply = (data: unknown) => Promise.resolve(new Response(JSON.stringify(data),
  { status: 200, headers: { "content-type": "application/json" } }));
afterEach(() => vi.restoreAllMocks());

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
    render(<GeneratedImagesPanel campaignId="c" />);
    await screen.findByText(/STORAGE_PENDING/);
    expect(screen.getByText(/Créditos previstos por geração: 15/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Gerar imagem" })).toBeDisabled();
    expect(screen.queryByText(/storage.googleapis.com/)).not.toBeInTheDocument();
    expect(calls).toHaveLength(2);
  });
});
