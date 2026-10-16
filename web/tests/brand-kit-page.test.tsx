import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import BrandKitPage from "@/app/(app)/(authenticated)/brand-kit/page";
import { setCsrfToken } from "@/lib/api/client";

const auth = vi.hoisted(() => ({ tenant: "a", manage: true }));
vi.mock("@/providers/AuthProvider", () => ({ useAuth: () => ({
  session: { tenant_id: auth.tenant, user_id: "owner" },
  me: { permissions: auth.manage ? ["BRAND_MANAGE"] : [], business_unit_id: "unit-a" },
}) }));
beforeEach(() => { auth.tenant = "a"; auth.manage = true; setCsrfToken("csrf-test-token"); });
afterEach(() => { vi.restoreAllMocks(); setCsrfToken(null); });


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
 
const original = { id: "fixture-brand", name: "Marca Original", tone: "claro",
  colors: ["#112233"], differentiators: ["Local"], restrictions: ["Sem garantia de resultado"],
  created_at: "2026-10-16T01:00:00Z", version: 1, updated_at: "2026-10-16T01:00:00Z" };
const revised = { ...original, tone: "direto", version: 2, updated_at: "2026-10-16T02:00:00Z" };

it("edita com a versão revisada e consulta o conteúdo anterior preservado", async () => {
  const user = userEvent.setup(); let changed = false;
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    if (init?.method === "PUT") { changed = true; return jsonResponse(200, revised); }
    if (url.endsWith("/versions")) return jsonResponse(200, { items: [revised, original], next_cursor: null });
    return jsonResponse(200, [changed ? revised : original]);
  });
  render(<BrandKitPage />);
  await user.click(await screen.findByRole("button", { name: "Editar Marca Original" }));
  await user.clear(screen.getByLabelText("Tom de voz")); await user.type(screen.getByLabelText("Tom de voz"), "direto");
  await user.click(screen.getByRole("button", { name: "Salvar alterações" }));
  await screen.findByText("Brand Kit salvo.");
  const put = fetch.mock.calls.find(([, init]) => init?.method === "PUT");
  expect(JSON.parse(String(put?.[1]?.body))).toMatchObject({ expected_version: 1, name: original.name, tone: "direto" });
  expect(new Headers(put?.[1]?.headers).get("x-csrf-token")).toBe("csrf-test-token");
  await user.click(screen.getByRole("button", { name: "Histórico de Marca Original" }));
  await screen.findByRole("heading", { name: "Versão 2 — Marca Original" });
  expect(screen.getByRole("heading", { name: "Versão 1 — Marca Original" })).toBeInTheDocument();
  expect(screen.getByText("Tom de voz: claro.")).toBeInTheDocument();
});

it("mantém o rascunho após conflito e exige revisar a versão atual antes de salvar", async () => {
  const user = userEvent.setup(); let refreshed = false;
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    if (init?.method === "PUT") { refreshed = true; return jsonResponse(409, { code: "BRAND_VERSION_CHANGED", message: "O Brand Kit mudou em outra edição." }); }
    return jsonResponse(200, [refreshed ? revised : original]);
  });
  render(<BrandKitPage />);
  await user.click(await screen.findByRole("button", { name: "Editar Marca Original" }));
  await user.clear(screen.getByLabelText("Tom de voz")); await user.type(screen.getByLabelText("Tom de voz"), "rascunho");
  await user.click(screen.getByRole("button", { name: "Salvar alterações" }));
  await screen.findByText("O Brand Kit mudou em outra edição.");
  expect(screen.getByLabelText("Tom de voz")).toHaveValue("rascunho");
  expect(fetch.mock.calls.filter(([, init]) => init?.method === "PUT")).toHaveLength(1);
  await user.click(screen.getByRole("button", { name: "Atualizar lista" }));
  await user.click(await screen.findByRole("button", { name: "Editar Marca Original" }));
  await screen.findByRole("heading", { name: "Editar Brand Kit — versão 2" });
  expect(screen.getByLabelText("Tom de voz")).toHaveValue("direto");
});

it("reutiliza a mesma criação após incerteza e bloqueia alterações do payload até confirmar", async () => {
  const user = userEvent.setup(); let attempts = 0;
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    if (init?.method === "POST") {
      attempts += 1;
      if (attempts === 1) return Promise.reject(new TypeError("lost create response"));
      return jsonResponse(201, original);
    }
    return jsonResponse(200, attempts > 1 ? [original] : []);
  });
  render(<BrandKitPage />);
  await screen.findByText("Nenhum Brand Kit ainda");
  await user.type(screen.getByLabelText("Nome"), original.name);
  await user.type(screen.getByLabelText("Tom de voz"), original.tone);
  await user.click(screen.getByRole("button", { name: "Salvar Brand Kit" }));
  await screen.findByText(/Resultado ainda não confirmado/);
  expect(screen.getByLabelText("Nome")).toBeDisabled();
  expect(screen.getByLabelText("Tom de voz")).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Salvar Brand Kit" }));
  await screen.findByText("Brand Kit salvo.");
  const writes = fetch.mock.calls.filter(([, init]) => init?.method === "POST");
  expect(writes[0][1]?.body).toBe(writes[1][1]?.body);
  expect(new Headers(writes[0][1]?.headers).get("idempotency-key")).toBe(new Headers(writes[1][1]?.headers).get("idempotency-key"));
});

it("reutiliza a mesma atualização após incerteza sem publicar uma revisão otimista", async () => {
  const user = userEvent.setup(); let attempts = 0;
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    if (init?.method === "PUT") {
      attempts += 1;
      return attempts === 1 ? Promise.reject(new TypeError("lost update response")) : jsonResponse(200, revised);
    }
    return jsonResponse(200, [attempts > 1 ? revised : original]);
  });
  render(<BrandKitPage />);
  await user.click(await screen.findByRole("button", { name: "Editar Marca Original" }));
  await user.clear(screen.getByLabelText("Tom de voz")); await user.type(screen.getByLabelText("Tom de voz"), "direto");
  await user.click(screen.getByRole("button", { name: "Salvar alterações" }));
  await screen.findByText(/Resultado ainda não confirmado/);
  expect(screen.getByText("claro", { exact: true })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Cancelar edição" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Salvar alterações" }));
  await screen.findByText("Brand Kit salvo.");
  const writes = fetch.mock.calls.filter(([, init]) => init?.method === "PUT");
  expect(writes[0][1]?.body).toBe(writes[1][1]?.body);
  expect(new Headers(writes[0][1]?.headers).get("idempotency-key")).toBe(new Headers(writes[1][1]?.headers).get("idempotency-key"));
});

it("permite consultar histórico sem oferecer edição para usuário sem BRAND_MANAGE", async () => {
  auth.manage = false;
  const user = userEvent.setup();
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
    String(input).endsWith("/versions") ? jsonResponse(200, { items: [original], next_cursor: null }) : jsonResponse(200, [original]));
  render(<BrandKitPage />);
  await screen.findByText("Marca Original", { exact: true });
  expect(screen.queryByRole("heading", { name: "Novo Brand Kit" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Editar Marca Original" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Histórico de Marca Original" }));
  await screen.findByRole("heading", { name: "Versão 1 — Marca Original" });
  expect(fetch.mock.calls.every(([, init]) => init?.method === "GET")).toBe(true);
});

it("descarta estado e resposta tardia de uma edição ao mudar de organização", async () => {
  const user = userEvent.setup();
  let resolvePut: (response: Response) => void = () => undefined;
  const beta = { ...original, id: "brand-beta", name: "Marca Beta" };
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    if (init?.method === "PUT") return new Promise<Response>(resolve => { resolvePut = resolve; });
    return jsonResponse(200, [auth.tenant === "a" ? original : beta]);
  });
  const view = render(<BrandKitPage />);
  await user.click(await screen.findByRole("button", { name: "Editar Marca Original" }));
  await user.click(screen.getByRole("button", { name: "Salvar alterações" }));
  auth.tenant = "b"; view.rerender(<BrandKitPage />);
  await screen.findByText("Marca Beta", { exact: true });
  await act(async () => { resolvePut(new Response(JSON.stringify(revised), { status: 200, headers: { "content-type": "application/json" } })); });
  expect(screen.queryByText("Marca Original", { exact: true })).not.toBeInTheDocument();
  expect(screen.getByLabelText("Nome")).toHaveValue("");
  expect(screen.queryByRole("heading", { name: /Editar Brand Kit/ })).not.toBeInTheDocument();
});
