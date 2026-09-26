import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import CampaignsPage from "@/app/(app)/(authenticated)/campaigns/page";
import { setCsrfToken } from "@/lib/api/client";

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

describe("CampaignsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setCsrfToken("csrf-test-token");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    setCsrfToken(null);
  });

  it("mostra estado vazio e cria uma campanha via briefing", async () => {
    let briefBody: unknown = null;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/briefs") && init?.method === "POST") {
        briefBody = JSON.parse(String(init.body));
        return jsonResponse(202, {
          id: "camp-1",
          name: "",
          objective: (briefBody as { objective: string }).objective,
          state: "DRAFT",
        });
      }
      if (url.endsWith("/campaigns")) return jsonResponse(200, { items: [] });
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<CampaignsPage />);

    await waitFor(() => expect(screen.getByText("Nenhuma campanha ainda")).toBeInTheDocument());

    await user.type(screen.getByLabelText("Objetivo"), "Gerar leads qualificados");
    await user.click(screen.getByRole("button", { name: /enviar briefing/i }));

    await waitFor(() => expect(screen.getByText("Gerar leads qualificados")).toBeInTheDocument());
    expect(briefBody).toMatchObject({ objective: "Gerar leads qualificados" });
  });
});
