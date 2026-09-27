import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "@/providers/AuthProvider";
import { TenantSwitcher } from "@/components/TenantSwitcher";

const DEMO_SESSION = {
  user_id: "user-multi-1a",
  tenant_id: "demo-tenant",
  business_unit_id: "bu-1",
  roles: ["OWNER"],
  csrf_token: "csrf-session-1",
};

const OTHER_SESSION = {
  user_id: "user-multi-1b",
  tenant_id: "other-tenant",
  business_unit_id: "bu-2",
  roles: ["OWNER"],
  csrf_token: "csrf-session-1",
};

const ME_BODY = {
  user_id: "user-multi-1a",
  tenant_id: "demo-tenant",
  business_unit_id: "bu-1",
  roles: ["OWNER"],
  permissions: ["CAMPAIGN_VIEW"],
  mfa_enabled: false,
};

const TWO_MEMBERSHIPS = {
  memberships: [
    {
      user_id: "user-multi-1a",
      tenant_id: "demo-tenant",
      business_unit_id: "bu-1",
      roles: ["OWNER"],
      active: true,
    },
    {
      user_id: "user-multi-1b",
      tenant_id: "other-tenant",
      business_unit_id: "bu-2",
      roles: ["OWNER"],
      active: false,
    },
  ],
};

const ONE_MEMBERSHIP = {
  memberships: [
    {
      user_id: "user-owner-1",
      tenant_id: "demo-tenant",
      business_unit_id: "bu-1",
      roles: ["OWNER"],
      active: true,
    },
  ],
};

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

function TenantLabel() {
  const { session } = useAuth();
  return <span data-testid="active-tenant">{session?.tenant_id ?? ""}</span>;
}

describe("TenantSwitcher", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("lista um unico vinculo sem oferecer troca", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/auth/session")) return jsonResponse(200, DEMO_SESSION);
      if (url.endsWith("/me/memberships")) return jsonResponse(200, ONE_MEMBERSHIP);
      if (url.endsWith("/me")) return jsonResponse(200, ME_BODY);
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(
      <AuthProvider>
        <TenantSwitcher />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByText(/apenas um tenant\/unidade/i)).toBeInTheDocument(),
    );
  });

  it("lista dois vinculos, mostra o ativo e permite trocar para o outro", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/auth/session/switch")) {
        return jsonResponse(200, OTHER_SESSION);
      }
      if (url.endsWith("/auth/session")) return jsonResponse(200, DEMO_SESSION);
      if (url.endsWith("/me/memberships")) return jsonResponse(200, TWO_MEMBERSHIPS);
      if (url.endsWith("/me")) return jsonResponse(200, ME_BODY);
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(
      <AuthProvider>
        <TenantLabel />
        <TenantSwitcher />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByText("Ativo")).toBeInTheDocument());
    expect(screen.getByText("other-tenant")).toBeInTheDocument();

    const switchButton = screen.getByTestId("switch-membership-user-multi-1b");
    await user.click(switchButton);

    await waitFor(() =>
      expect(screen.getByTestId("active-tenant").textContent).toBe("other-tenant"),
    );
  });

  it("mostra erro quando o backend recusa a troca (vinculo nao pertence a identidade)", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/auth/session/switch")) {
        return jsonResponse(403, {
          code: "PERMISSION_DENIED",
          message: "O vinculo solicitado nao pertence a esta identidade.",
        });
      }
      if (url.endsWith("/auth/session")) return jsonResponse(200, DEMO_SESSION);
      if (url.endsWith("/me/memberships")) return jsonResponse(200, TWO_MEMBERSHIPS);
      if (url.endsWith("/me")) return jsonResponse(200, ME_BODY);
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(
      <AuthProvider>
        <TenantSwitcher />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("switch-membership-user-multi-1b")).toBeInTheDocument(),
    );
    await user.click(screen.getByTestId("switch-membership-user-multi-1b"));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByText(/nao pertence a esta identidade/i)).toBeInTheDocument();
  });
});
