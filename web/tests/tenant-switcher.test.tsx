import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TenantSwitcher } from "@/components/TenantSwitcher";

const SINGLE = [{ tenant_id: "demo-tenant", business_unit_id: "bu-1", roles: ["OWNER"], is_active: true }];
const MULTI = [
  { tenant_id: "demo-tenant", business_unit_id: "bu-1", roles: ["OWNER"], is_active: true },
  { tenant_id: "other-tenant", business_unit_id: "bu-2", roles: ["VIEWER"], is_active: false },
];

describe("TenantSwitcher", () => {
  const originalCookie = document.cookie;

  beforeEach(() => {
    document.cookie = "campaia_csrf=real-csrf-token-value";
  });

  afterEach(() => {
    document.cookie = originalCookie;
    vi.restoreAllMocks();
  });

  it("renders nothing when the user has only one membership", () => {
    const { container } = render(
      <TenantSwitcher bffOrigin="https://bff.example" memberships={SINGLE} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a select with every membership when there is more than one", () => {
    render(<TenantSwitcher bffOrigin="https://bff.example" memberships={MULTI} />);
    const select = screen.getByLabelText("Tenant ativo");
    expect(select).toHaveValue("demo-tenant");
    expect(screen.getByRole("option", { name: /demo-tenant/ })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /other-tenant/ })).toBeInTheDocument();
  });

  it("POSTs the chosen tenant_id with the CSRF header and reloads on success", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("location", { ...window.location, reload: vi.fn() });

    render(<TenantSwitcher bffOrigin="https://bff.example" memberships={MULTI} />);
    await userEvent.selectOptions(screen.getByLabelText("Tenant ativo"), "other-tenant");

    expect(fetchMock).toHaveBeenCalledWith(
      "https://bff.example/session/switch-tenant",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": "real-csrf-token-value",
        },
        body: JSON.stringify({ tenant_id: "other-tenant" }),
      }),
    );
  });

  it("shows an error and never calls fetch when no CSRF cookie is present", async () => {
    document.cookie = "campaia_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<TenantSwitcher bffOrigin="https://bff.example" memberships={MULTI} />);
    await userEvent.selectOptions(screen.getByLabelText("Tenant ativo"), "other-tenant");

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("shows an error message when the switch request is denied", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 403 });
    vi.stubGlobal("fetch", fetchMock);

    render(<TenantSwitcher bffOrigin="https://bff.example" memberships={MULTI} />);
    await userEvent.selectOptions(screen.getByLabelText("Tenant ativo"), "other-tenant");

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
