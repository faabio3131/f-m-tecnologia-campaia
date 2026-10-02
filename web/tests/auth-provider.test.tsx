import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "@/providers/AuthProvider";
import { getCsrfToken } from "@/lib/api/client";

const SESSION_BODY = {
  user_id: "user-owner-1",
  tenant_id: "demo-tenant",
  business_unit_id: "bu-1",
  roles: ["OWNER"],
  csrf_token: "csrf-session-1",
};

const ME_BODY = {
  user_id: "user-owner-1",
  tenant_id: "demo-tenant",
  business_unit_id: "bu-1",
  roles: ["OWNER"],
  permissions: ["CAMPAIGN_VIEW"],
  mfa_enabled: false,
};

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

function Probe() {
  const { status, session, me, logout } = useAuth();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="user">{session?.user_id ?? ""}</span>
      <span data-testid="roles">{me?.roles?.join(",") ?? ""}</span>
      <button onClick={() => logout()}>logout</button>
    </div>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("bootstraps to authenticated on 200 from /auth/session + /me", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/auth/session")) return jsonResponse(200, SESSION_BODY);
      if (url.endsWith("/me")) return jsonResponse(200, ME_BODY);
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    expect(screen.getByTestId("status").textContent).toBe("bootstrapping");
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));
    expect(screen.getByTestId("user").textContent).toBe("user-owner-1");
    expect(screen.getByTestId("roles").textContent).toBe("OWNER");
    expect(getCsrfToken()).toBe("csrf-session-1");
  });

  it("bootstraps to unauthenticated on 401 from /auth/session", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(401, { code: "UNAUTHENTICATED", message: "Sem sessao." }),
    );

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated"),
    );
    expect(getCsrfToken()).toBeNull();
  });

  it("logout clears the auth context and the in-memory CSRF token", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/auth/session") && init?.method === "DELETE") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.endsWith("/auth/session")) return jsonResponse(200, SESSION_BODY);
      if (url.endsWith("/me")) return jsonResponse(200, ME_BODY);
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));

    await user.click(screen.getByText("logout"));

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated"),
    );
    expect(screen.getByTestId("user").textContent).toBe("");
    expect(getCsrfToken()).toBeNull();
  });

  it("logout still clears local state even if the DELETE call fails (already-invalid session)", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/auth/session") && init?.method === "DELETE") {
        return jsonResponse(401, { code: "UNAUTHENTICATED", message: "Ja invalida." });
      }
      if (url.endsWith("/auth/session")) return jsonResponse(200, SESSION_BODY);
      if (url.endsWith("/me")) return jsonResponse(200, ME_BODY);
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));
    await user.click(screen.getByText("logout"));

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated"),
    );
  });

  it("any 401 from a later API call clears the auth context (global listener)", async () => {
    let meCallCount = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/auth/session")) return jsonResponse(200, SESSION_BODY);
      if (url.endsWith("/me")) {
        meCallCount += 1;
        return jsonResponse(200, ME_BODY);
      }
      if (url.endsWith("/campaigns")) {
        return jsonResponse(401, { code: "UNAUTHENTICATED", message: "Sessao expirou." });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));
    expect(meCallCount).toBe(1);

    const { api } = await import("@/lib/api/client");
    await api.get("/campaigns").catch(() => undefined);

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated"),
    );
  });
});
