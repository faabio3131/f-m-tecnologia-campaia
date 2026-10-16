import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CampaignBrandSnapshot } from "@/components/CampaignBrandSnapshot";

describe("CampaignBrandSnapshot", () => {
  it("shows frozen guidance and reports an unavailable selected image", async () => {
    render(<CampaignBrandSnapshot snapshot={{
      profile: { id: "bp-1", name: "Marca registrada", tone: "claro", version: 3,
        colors: ["#112233"], restrictions: ["Não prometer retorno garantido."] },
      recorded_at: "2026-10-16T00:00:00Z",
      assets: [{ id: "asset-1", brand_profile_id: "bp-1", kind: "LOGO", status: "READY",
        width: 2, height: 3, size_bytes: 80, content_type: "image/png",
        created_at: "2026-10-16T00:00:00Z", updated_at: "2026-10-16T00:00:00Z",
        content_url: "/api/campaia/brand-profiles/bp-1/assets/asset-1/content" }],
    }} />);
    expect(screen.getByText("Marca registrada · versão 3")).toBeInTheDocument();
    expect(screen.getByText("Não prometer retorno garantido.")).toBeInTheDocument();
    fireEvent.error(screen.getByRole("img", { name: "Arquivo selecionado de Marca registrada" }));
    expect(await screen.findByText(/crie um novo briefing com arquivos disponíveis/)).toBeInTheDocument();
  });
});
