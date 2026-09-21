import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConnectAccountCard } from "@/components/ConnectAccountCard";

const CONNECTION = {
  id: "conn-1",
  provider: "GOOGLE_ADS" as const,
  external_account_id: "acc-1",
  display_name: "Google Ads (simulado)",
  status: "ACTIVE" as const,
  api_version: "sim-1",
  last_synced_at: "2026-01-01T00:00:00Z",
};

describe("ConnectAccountCard", () => {
  const originalCookie = document.cookie;

  beforeEach(() => {
    document.cookie = "campaia_csrf=real-csrf-token-value";
    vi.stubGlobal("crypto", { randomUUID: () => "fixed-idempotency-key" });
  });

  afterEach(() => {
    document.cookie = originalCookie;
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("shows 'Não conectado' and a Connect button when no connection exists", () => {
    render(
      <ConnectAccountCard
        bffOrigin="https://bff.example"
        provider="GOOGLE_ADS"
        label="Google Ads"
        connection={undefined}
      />,
    );
    expect(screen.getByText("Não conectado")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Conectar (simulado)" })).toBeInTheDocument();
  });

  it("shows the connected account and no button when a connection exists", () => {
    render(
      <ConnectAccountCard
        bffOrigin="https://bff.example"
        provider="GOOGLE_ADS"
        label="Google Ads"
        connection={CONNECTION}
      />,
    );
    expect(screen.getByText("Conectado (simulado)")).toBeInTheDocument();
    expect(screen.getByText("Google Ads (simulado)")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Conectar (simulado)" })).not.toBeInTheDocument();
  });

  it("calls start then complete with CSRF, step-up marker, and idempotency key, then reloads", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ state: "abcdefgh-state" }) })
      .mockResolvedValueOnce({ ok: true, status: 201 });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("location", { ...window.location, reload: vi.fn() });

    render(
      <ConnectAccountCard
        bffOrigin="https://bff.example"
        provider="GOOGLE_ADS"
        label="Google Ads"
        connection={undefined}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Conectar (simulado)" }));

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://bff.example/connections/oauth/start",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": "real-csrf-token-value",
          "x-step-up-token": "web-ui-connect-account-button-clicked",
        },
        body: JSON.stringify({ provider: "GOOGLE_ADS" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://bff.example/connections/oauth/complete",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": "real-csrf-token-value",
          "x-step-up-token": "web-ui-connect-account-button-clicked",
          "idempotency-key": "fixed-idempotency-key",
        },
        body: JSON.stringify({
          state: "abcdefgh-state",
          external_account_id: "sim-google_ads-abcdefgh",
          display_name: "Google Ads (simulado)",
        }),
      }),
    );
  });

  it("shows an error and never calls fetch when no CSRF cookie is present", async () => {
    document.cookie = "campaia_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ConnectAccountCard
        bffOrigin="https://bff.example"
        provider="GOOGLE_ADS"
        label="Google Ads"
        connection={undefined}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Conectar (simulado)" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("shows an error when the start call fails, without calling complete", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 403 });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ConnectAccountCard
        bffOrigin="https://bff.example"
        provider="GOOGLE_ADS"
        label="Google Ads"
        connection={undefined}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Conectar (simulado)" }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("shows an error when the complete call fails", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ state: "abcdefgh-state" }) })
      .mockResolvedValueOnce({ ok: false, status: 422 });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ConnectAccountCard
        bffOrigin="https://bff.example"
        provider="GOOGLE_ADS"
        label="Google Ads"
        connection={undefined}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Conectar (simulado)" }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
