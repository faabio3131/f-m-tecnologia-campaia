import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setCsrfToken } from "@/lib/api/client";
import { CapabilitiesPanel } from "@/components/CapabilitiesPanel";

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

// Reflete o formato REAL de GET /connections/{id}/capabilities, incluindo
// `provider`/`country`/`api_version`, campos aditivos ao contrato encontrados nesta
// reconciliação (WP-09) -- ver contracts/bff-openapi.yaml.
const CAPABILITIES = [
  {
    provider: "GOOGLE_ADS",
    capability_key: "PUBLISH:GOOGLE_ADS",
    country: "BR",
    api_version: "v1",
    supported: true,
    requires_approval: false,
    evidence_url: null,
    verified_at: "2026-09-26T00:00:00Z",
    notes: "Simulated capability, verified in-process at startup.",
  },
  {
    provider: "GOOGLE_ADS",
    capability_key: "PUBLISH:META_ADS",
    country: "BR",
    api_version: "v1",
    supported: false,
    requires_approval: false,
    evidence_url: null,
    verified_at: "2026-09-26T00:00:00Z",
    notes: null,
  },
];

describe("CapabilitiesPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setCsrfToken("csrf-test-token");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    setCsrfToken(null);
  });

  it("não busca nada até o usuário clicar em 'Ver capacidades'", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<CapabilitiesPanel connectionId="conn-1" />);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("busca e mostra as capacidades reais ao expandir, incluindo suportada e não suportada", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/connections/conn-1/capabilities") && init?.method === "GET") {
        return jsonResponse(200, CAPABILITIES);
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<CapabilitiesPanel connectionId="conn-1" />);

    await user.click(screen.getByTestId("toggle-capabilities-conn-1"));

    await waitFor(() => expect(screen.getByText("PUBLISH:GOOGLE_ADS")).toBeInTheDocument());
    expect(screen.getByText("PUBLISH:META_ADS")).toBeInTheDocument();
    expect(screen.getByText("Suportada")).toBeInTheDocument();
    expect(screen.getByText("Não suportada")).toBeInTheDocument();
    // evidence_url null nunca e inventado -- mostrado honestamente.
    expect(screen.getAllByText(/sem evidência registrada/i).length).toBeGreaterThan(0);
  });

  it("busca só uma vez ao alternar mostrar/ocultar repetidamente", async () => {
    let callCount = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/connections/conn-1/capabilities") && init?.method === "GET") {
        callCount += 1;
        return jsonResponse(200, CAPABILITIES);
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<CapabilitiesPanel connectionId="conn-1" />);

    await user.click(screen.getByTestId("toggle-capabilities-conn-1"));
    await waitFor(() => expect(callCount).toBe(1));
    await user.click(screen.getByTestId("toggle-capabilities-conn-1")); // ocultar
    await user.click(screen.getByTestId("toggle-capabilities-conn-1")); // mostrar de novo

    expect(callCount).toBe(1);
  });
});
