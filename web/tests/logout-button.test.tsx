import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LogoutButton } from "@/components/LogoutButton";

describe("LogoutButton", () => {
  const originalCookie = document.cookie;

  beforeEach(() => {
    document.cookie = "campaia_csrf=real-csrf-token-value";
  });

  afterEach(() => {
    document.cookie = originalCookie;
    vi.restoreAllMocks();
  });

  it("sends the CSRF cookie value as the X-CSRF-Token header on logout", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 302 });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("location", { ...window.location, reload: vi.fn() });

    render(<LogoutButton bffOrigin="https://bff.example" />);
    await userEvent.click(screen.getByRole("button", { name: "Sair" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "https://bff.example/auth/logout",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: { "x-csrf-token": "real-csrf-token-value" },
      }),
    );
  });

  it("shows an error and never calls fetch when no CSRF cookie is present", async () => {
    document.cookie = "campaia_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<LogoutButton bffOrigin="https://bff.example" />);
    await userEvent.click(screen.getByRole("button", { name: "Sair" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("shows an error message when the logout request fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    vi.stubGlobal("fetch", fetchMock);

    render(<LogoutButton bffOrigin="https://bff.example" />);
    await userEvent.click(screen.getByRole("button", { name: "Sair" }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
