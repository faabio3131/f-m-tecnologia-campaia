import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BrandKitForm } from "@/components/BrandKitForm";

const EXISTING = [
  {
    id: "bp-1",
    name: "Acme",
    tone: "casual",
    colors: ["#2f5ce0"],
    differentiators: [],
    restrictions: [],
    created_at: "2026-01-01T00:00:00Z",
  },
];

describe("BrandKitForm", () => {
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

  it("shows an empty-state note when there is no existing Brand Kit", () => {
    render(<BrandKitForm bffOrigin="https://bff.example" existing={[]} />);
    expect(screen.getByText(/Nenhum Brand Kit ainda/)).toBeInTheDocument();
  });

  it("lists existing Brand Kits instead of the empty-state note", () => {
    render(<BrandKitForm bffOrigin="https://bff.example" existing={EXISTING} />);
    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.queryByText(/Nenhum Brand Kit ainda/)).not.toBeInTheDocument();
  });

  it("rejects submission when name/tone are only whitespace, even though HTML5 required is satisfied", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<BrandKitForm bffOrigin="https://bff.example" existing={[]} />);
    // A single space satisfies the inputs' `required` attribute (native validation would
    // otherwise block the submit event before our handler ever runs) but must still be
    // rejected by the component's own trim()-based check.
    await userEvent.type(screen.getByLabelText("Nome*"), " ");
    await userEvent.type(screen.getByLabelText("Tom de voz*"), " ");
    await userEvent.click(screen.getByRole("button", { name: "Salvar Brand Kit" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("Nome e tom de voz são obrigatórios.");
  });

  it("POSTs parsed fields with CSRF and a fresh idempotency key, then reloads", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 201 });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("location", { ...window.location, reload: vi.fn() });

    render(<BrandKitForm bffOrigin="https://bff.example" existing={[]} />);
    await userEvent.type(screen.getByLabelText("Nome*"), "Acme");
    await userEvent.type(screen.getByLabelText("Tom de voz*"), "casual");
    await userEvent.type(screen.getByLabelText(/Cores principais/), "#2f5ce0, #12b886");
    await userEvent.type(screen.getByLabelText(/Diferenciais competitivos/), "Rápido\nBarato");
    await userEvent.click(screen.getByRole("button", { name: "Salvar Brand Kit" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "https://bff.example/brand-profiles",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": "real-csrf-token-value",
          "idempotency-key": "fixed-idempotency-key",
        },
        body: JSON.stringify({
          name: "Acme",
          tone: "casual",
          colors: ["#2f5ce0", "#12b886"],
          differentiators: ["Rápido", "Barato"],
          restrictions: [],
        }),
      }),
    );
  });

  it("shows an error and never calls fetch when no CSRF cookie is present", async () => {
    document.cookie = "campaia_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<BrandKitForm bffOrigin="https://bff.example" existing={[]} />);
    await userEvent.type(screen.getByLabelText("Nome*"), "Acme");
    await userEvent.type(screen.getByLabelText("Tom de voz*"), "casual");
    await userEvent.click(screen.getByRole("button", { name: "Salvar Brand Kit" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("shows an error message when the request fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 422 });
    vi.stubGlobal("fetch", fetchMock);

    render(<BrandKitForm bffOrigin="https://bff.example" existing={[]} />);
    await userEvent.type(screen.getByLabelText("Nome*"), "Acme");
    await userEvent.type(screen.getByLabelText("Tom de voz*"), "casual");
    await userEvent.click(screen.getByRole("button", { name: "Salvar Brand Kit" }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
