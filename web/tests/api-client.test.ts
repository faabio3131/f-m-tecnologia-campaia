import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ApiClientError,
  CsrfUnavailableError,
  api,
  setCsrfToken,
  setUnauthenticatedListener,
} from "@/lib/api/client";

function mockFetchResponse(init: {
  status: number;
  body?: unknown;
}): Promise<Response> {
  const text = init.body === undefined ? "" : JSON.stringify(init.body);
  return Promise.resolve(
    new Response(text, {
      status: init.status,
      headers: { "content-type": "application/json" },
    }),
  );
}

describe("api client", () => {
  beforeEach(() => {
    setCsrfToken(null);
    setUnauthenticatedListener(null);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    setCsrfToken(null);
    setUnauthenticatedListener(null);
  });

  it("sends credentials: include on every request", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => mockFetchResponse({ status: 200, body: { ok: true } }));

    await api.get("/me");

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [, requestInit] = fetchSpy.mock.calls[0];
    expect(requestInit).toMatchObject({ credentials: "include" });
  });

  it("GET does not require a CSRF token", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      mockFetchResponse({ status: 200, body: { ok: true } }),
    );

    await expect(api.get("/me")).resolves.toEqual({ ok: true });
  });

  it("POST sends X-CSRF-Token when a token is set", async () => {
    setCsrfToken("csrf-abc");
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => mockFetchResponse({ status: 201, body: { id: "1" } }));

    await api.post("/brand-profiles", { name: "X" });

    const [, requestInit] = fetchSpy.mock.calls[0];
    const headers = requestInit?.headers as Headers;
    expect(headers.get("x-csrf-token")).toBe("csrf-abc");
  });

  it("blocks a mutation locally when no CSRF token is available, without calling fetch", async () => {
    setCsrfToken(null);
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    await expect(api.post("/brand-profiles", { name: "X" })).rejects.toBeInstanceOf(
      CsrfUnavailableError,
    );
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("throws ApiClientError with the canonical error body on non-2xx", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      mockFetchResponse({
        status: 403,
        body: { code: "PERMISSION_DENIED", message: "Sem permissao.", details: null },
      }),
    );

    const error = await api.get("/campaigns").catch((e) => e);
    expect(error).toBeInstanceOf(ApiClientError);
    expect((error as ApiClientError).status).toBe(403);
    expect((error as ApiClientError).code).toBe("PERMISSION_DENIED");
  });

  it("calls the unauthenticated listener on any 401 response", async () => {
    const listener = vi.fn();
    setUnauthenticatedListener(listener);
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      mockFetchResponse({
        status: 401,
        body: { code: "UNAUTHENTICATED", message: "Sessao invalida." },
      }),
    );

    await api.get("/me").catch(() => undefined);

    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("never calls the unauthenticated listener on a 403", async () => {
    const listener = vi.fn();
    setUnauthenticatedListener(listener);
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      mockFetchResponse({
        status: 403,
        body: { code: "PERMISSION_DENIED", message: "Sem permissao." },
      }),
    );

    await api.get("/campaigns").catch(() => undefined);

    expect(listener).not.toHaveBeenCalled();
  });

  it("sends the Idempotency-Key header when provided, unchanged across retries of the same action", async () => {
    setCsrfToken("csrf-abc");
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => mockFetchResponse({ status: 202, body: { id: "1" } }));

    const key = "stable-idempotency-key-001";
    await api.post("/briefs", { objective: "x" }, { idempotencyKey: key });
    await api.post("/briefs", { objective: "x" }, { idempotencyKey: key });

    for (const call of fetchSpy.mock.calls) {
      const headers = call[1]?.headers as Headers;
      expect(headers.get("idempotency-key")).toBe(key);
    }
  });
});
