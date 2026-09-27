import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import BrandKitPage from "@/app/(app)/(authenticated)/brand-kit/page";
import { setCsrfToken } from "@/lib/api/client";

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

describe("BrandKitPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setCsrfToken("csrf-test-token");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    setCsrfToken(null);
  });

  it("mostra estado vazio quando nao ha brand kits", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/brand-profiles")) return jsonResponse(200, []);
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(<BrandKitPage />);

    await waitFor(() =>
      expect(screen.getByText(/nenhum brand kit ainda/i)).toBeInTheDocument(),
    );
  });

  it("lista brand kits existentes", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith("/brand-profiles")) {
        return jsonResponse(200, [
          { id: "bp-1", name: "Marca Principal", tone: "casual", colors: [], differentiators: [], restrictions: [] },
        ]);
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(<BrandKitPage />);

    await waitFor(() => expect(screen.getByText("Marca Principal")).toBeInTheDocument());
    expect(screen.getByText("casual")).toBeInTheDocument();
  });

  it("envia POST /brand-profiles com os campos do formulario e recarrega a lista", async () => {
    let createBody: unknown = null;
    let listCallCount = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/brand-profiles") && init?.method === "POST") {
        createBody = JSON.parse(String(init.body));
        return jsonResponse(201, { id: "bp-2", ...(createBody as object) });
      }
      if (url.endsWith("/brand-profiles")) {
        listCallCount += 1;
        return jsonResponse(200, listCallCount === 1 ? [] : [{ id: "bp-2", name: "Nova Marca", tone: "formal" }]);
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<BrandKitPage />);

    await waitFor(() => expect(screen.getByText(/nenhum brand kit ainda/i)).toBeInTheDocument());

    await user.type(screen.getByLabelText("Nome"), "Nova Marca");
    await user.type(screen.getByLabelText("Tom de voz"), "formal");
    await user.click(screen.getByRole("button", { name: /salvar brand kit/i }));

    await waitFor(() => expect(screen.getByText("Nova Marca")).toBeInTheDocument());
    expect(createBody).toMatchObject({ name: "Nova Marca", tone: "formal" });
  });

  it("mostra erro quando o backend recusa a criacao", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/brand-profiles") && init?.method === "POST") {
        return jsonResponse(403, { code: "PERMISSION_DENIED", message: "Sem permissao para gerenciar marca." });
      }
      if (url.endsWith("/brand-profiles")) return jsonResponse(200, []);
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<BrandKitPage />);

    await waitFor(() => expect(screen.getByText(/nenhum brand kit ainda/i)).toBeInTheDocument());

    await user.type(screen.getByLabelText("Nome"), "X");
    await user.type(screen.getByLabelText("Tom de voz"), "Y");
    await user.click(screen.getByRole("button", { name: /salvar brand kit/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByText(/sem permissao para gerenciar marca/i)).toBeInTheDocument();
  });
});
