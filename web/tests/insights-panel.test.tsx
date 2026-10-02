import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setCsrfToken } from "@/lib/api/client";
import { InsightsPanel } from "@/components/InsightsPanel";

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

describe("InsightsPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setCsrfToken("csrf-test-token");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    setCsrfToken(null);
  });

  it("mostra a nota honesta do backend quando points vem vazio", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/campaigns/camp-1/insights")) {
        return jsonResponse(200, {
          campaign_id: "camp-1",
          points: [],
          last_synced_at: null,
          note: "No analytics layer implemented yet in campaia_core; this is an honest placeholder, not fabricated data.",
        });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(<InsightsPanel campaignId="camp-1" />);

    await waitFor(() =>
      expect(screen.getByText(/honest placeholder, not fabricated data/i)).toBeInTheDocument(),
    );
    // Nunca deve inventar um grafico ou placeholder generico quando points vem vazio.
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("lista pontos reais quando o backend devolve dados", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/campaigns/camp-2/insights")) {
        return jsonResponse(200, {
          campaign_id: "camp-2",
          points: [
            {
              date: "2026-09-25",
              channel: "GOOGLE_ADS",
              impressions: 1000,
              clicks: 50,
              spend: "120.00",
              conversions: 3,
              cpa: "40.00",
            },
          ],
          last_synced_at: "2026-09-25T10:00:00Z",
          note: "ok",
        });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(<InsightsPanel campaignId="camp-2" />);

    await waitFor(() => expect(screen.getByText(/1000 impressões/i)).toBeInTheDocument());
    expect(screen.getByText(/50 cliques/i)).toBeInTheDocument();
    expect(screen.getByText(/3 conversões/i)).toBeInTheDocument();
  });

  it("mostra um erro honesto quando GET /insights falha", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/campaigns/camp-3/insights")) {
        return jsonResponse(500, { code: "INTERNAL", message: "erro interno" });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(<InsightsPanel campaignId="camp-3" />);

    await waitFor(() =>
      expect(screen.getByText(/não foi possível carregar as métricas/i)).toBeInTheDocument(),
    );
  });
});
