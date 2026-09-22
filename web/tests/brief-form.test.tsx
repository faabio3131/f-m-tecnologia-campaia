import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BriefForm } from "@/components/BriefForm";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

describe("BriefForm", () => {
  const originalCookie = document.cookie;

  beforeEach(() => {
    document.cookie = "campaia_csrf=real-csrf-token-value";
    vi.stubGlobal("crypto", { randomUUID: () => "fixed-idempotency-key" });
    pushMock.mockClear();
  });

  afterEach(() => {
    document.cookie = originalCookie;
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("rejects submission when objective is only whitespace, even though HTML5 required is satisfied", async () => {
    render(<BriefForm bffOrigin="https://bff.example" />);
    // A single space satisfies the native `required` attribute (jsdom blocks the submit
    // event entirely for a truly empty required field, before React's onSubmit ever runs)
    // while still failing the component's own .trim() check -- same pattern established by
    // WP-04's brand-kit-form.test.tsx.
    await userEvent.type(screen.getByLabelText("Objetivo*"), " ");
    await userEvent.click(screen.getByRole("button", { name: "Enviar briefing" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Objetivo é obrigatório.");
  });

  it("rejects submission with no channel selected", async () => {
    render(<BriefForm bffOrigin="https://bff.example" />);
    await userEvent.type(screen.getByLabelText("Objetivo*"), "Gerar leads");
    await userEvent.click(screen.getByLabelText("Google Ads"));
    await userEvent.click(screen.getByRole("button", { name: "Enviar briefing" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Selecione ao menos um canal.");
  });

  it("submits the brief with CSRF/idempotency headers and redirects to the new campaign", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({ id: "camp-1" }) });
    vi.stubGlobal("fetch", fetchMock);

    render(<BriefForm bffOrigin="https://bff.example" />);
    await userEvent.type(screen.getByLabelText("Objetivo*"), "Gerar leads qualificados");
    await userEvent.click(screen.getByRole("button", { name: "Enviar briefing" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "https://bff.example/briefs",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": "real-csrf-token-value",
          "idempotency-key": "fixed-idempotency-key",
        },
      }),
    );
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body).toMatchObject({
      objective: "Gerar leads qualificados",
      channels: ["GOOGLE_ADS"],
      total_budget: "10000",
      daily_cap: "1000",
    });
    expect(pushMock).toHaveBeenCalledWith("/campaigns/camp-1");
  });

  it("shows an error and never calls fetch when no CSRF cookie is present", async () => {
    document.cookie = "campaia_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<BriefForm bffOrigin="https://bff.example" />);
    await userEvent.type(screen.getByLabelText("Objetivo*"), "Gerar leads");
    await userEvent.click(screen.getByRole("button", { name: "Enviar briefing" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("shows an error when the request fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 422 });
    vi.stubGlobal("fetch", fetchMock);

    render(<BriefForm bffOrigin="https://bff.example" />);
    await userEvent.type(screen.getByLabelText("Objetivo*"), "Gerar leads");
    await userEvent.click(screen.getByRole("button", { name: "Enviar briefing" }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });
});
