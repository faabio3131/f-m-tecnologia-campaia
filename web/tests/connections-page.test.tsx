import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ConnectionsPage from "@/app/(app)/(authenticated)/connections/page";
import { setCsrfToken } from "@/lib/api/client";

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

describe("ConnectionsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setCsrfToken("csrf-test-token");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    setCsrfToken(null);
  });

  it("lista os 3 provedores, todos nao conectados quando a lista esta vazia", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/connections")) return jsonResponse(200, []);
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(<ConnectionsPage />);

    await waitFor(() => expect(screen.getAllByText("Não conectado")).toHaveLength(3));
    expect(screen.getByText("Google Ads")).toBeInTheDocument();
    expect(screen.getByText("Meta (Facebook/Instagram)")).toBeInTheDocument();
    expect(screen.getByText("WhatsApp Business")).toBeInTheDocument();
  });

  it("mostra uma conexao ativa e nao oferece 'Conectar' para ela", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/connections")) {
        return jsonResponse(200, [
          {
            id: "conn-1",
            provider: "GOOGLE_ADS",
            external_account_id: "acct-1",
            display_name: "Conta Principal",
            status: "ACTIVE",
            api_version: "sim-1",
            last_synced_at: null,
          },
        ]);
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(<ConnectionsPage />);

    await waitFor(() =>
      expect(screen.getByText(/conectado — conta principal/i)).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("connect-GOOGLE_ADS")).not.toBeInTheDocument();
    expect(screen.getByTestId("connect-META")).toBeInTheDocument();
  });

  it("fluxo completo: confirmar -> start -> selecionar conta -> callback -> lista atualizada", async () => {
    let connectionsCallCount = 0;
    let startBody: unknown = null;
    let callbackBody: unknown = null;

    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/connections/oauth/start")) {
        startBody = JSON.parse(String(init?.body));
        return jsonResponse(200, {
          authorization_url: "https://auth.simulated-ads-provider.invalid/x",
          state: "state-abc",
        });
      }
      if (url.endsWith("/connections/oauth/callback")) {
        callbackBody = JSON.parse(String(init?.body));
        return jsonResponse(201, {
          id: "conn-1",
          provider: "GOOGLE_ADS",
          external_account_id: "acct-real-1",
          display_name: "Conta Real",
          status: "ACTIVE",
          api_version: "sim-1",
          last_synced_at: null,
        });
      }
      if (url.endsWith("/connections")) {
        connectionsCallCount += 1;
        if (connectionsCallCount === 1) return jsonResponse(200, []);
        return jsonResponse(200, [
          {
            id: "conn-1",
            provider: "GOOGLE_ADS",
            external_account_id: "acct-real-1",
            display_name: "Conta Real",
            status: "ACTIVE",
            api_version: "sim-1",
            last_synced_at: null,
          },
        ]);
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<ConnectionsPage />);

    await waitFor(() => expect(screen.getByTestId("connect-GOOGLE_ADS")).toBeInTheDocument());
    await user.click(screen.getByTestId("connect-GOOGLE_ADS"));

    await waitFor(() =>
      expect(screen.getByText(/esta ação exige reautenticação recente/i)).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /confirmar e conectar/i }));

    await waitFor(() => expect(startBody).toMatchObject({ provider: "GOOGLE_ADS" }));
    await waitFor(() =>
      expect(screen.getByTestId(`complete-connection-GOOGLE_ADS`)).toBeInTheDocument(),
    );

    await user.type(screen.getByLabelText("ID da conta"), "acct-real-1");
    await user.type(screen.getByLabelText("Nome de exibição"), "Conta Real");
    await user.click(screen.getByTestId("complete-connection-GOOGLE_ADS"));

    await waitFor(() =>
      expect(callbackBody).toMatchObject({
        state: "state-abc",
        external_account_id: "acct-real-1",
        display_name: "Conta Real",
      }),
    );
    await waitFor(() =>
      expect(screen.getByText(/conectado — conta real/i)).toBeInTheDocument(),
    );
  });
});
