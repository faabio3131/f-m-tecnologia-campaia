import { test, expect, type Page } from "@playwright/test";
import { deflateSync } from "node:zlib";

/**
 * E2E real do protocolo de sessao (Etapa 2, secoes 29-30). Roda contra o Next.js
 * real (dev server) + o backend Starlette real com o harness de E2E
 * (backend/tests_support/e2e_server.py) -- nunca um mock de rede. Ver
 * playwright.session.config.ts.
 */


function smallStaticPng() {
  function chunk(kind: string, data: Buffer) {
    const label = Buffer.from(kind);
    const payload = Buffer.concat([label, data]);
    let crc = 0xffffffff;
    for (const byte of payload) {
      crc ^= byte;
      for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
    }
    const length = Buffer.alloc(4), checksum = Buffer.alloc(4);
    length.writeUInt32BE(data.length); checksum.writeUInt32BE((crc ^ 0xffffffff) >>> 0);
    return Buffer.concat([length, payload, checksum]);
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(2, 0); header.writeUInt32BE(3, 4); header[8] = 8; header[9] = 2;
  const pixels = Buffer.from([0, 255, 0, 0, 255, 0, 0]);
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk("IHDR", header), chunk("IDAT", deflateSync(Buffer.concat([pixels, pixels, pixels]))), chunk("IEND", Buffer.alloc(0))]);
}

const TENANT_A_TESTID = "test-identity-e2e-test-id-token-tenant-a-owner";
const TENANT_B_TESTID = "test-identity-e2e-test-id-token-tenant-b-owner";
const UNVERIFIED_TESTID = "test-identity-e2e-test-id-token-unverified-email";
const UNKNOWN_TESTID = "test-identity-e2e-test-id-token-unknown-email";
const MULTI_TENANT_TESTID = "test-identity-e2e-test-id-token-multi-tenant-owner";

/**
 * Clica no login de teste e devolve o corpo real de POST /auth/session.
 *
 * Filtra explicitamente por metodo POST: a pagina de login tambem monta o
 * AuthProvider (que sempre dispara um GET /auth/session de bootstrap ao montar,
 * mesmo sem sessao) -- sem esse filtro, `waitForResponse` pode capturar por engano
 * essa GET 401 do bootstrap em vez da POST do login (race de rede real).
 *
 * Depois espera o cookie `campaia_session` aparecer no cookie jar do
 * BrowserContext antes de devolver -- `page.request` (usado pelos testes para
 * chamadas diretas ao BFF) le desse mesmo cookie jar, mas a sincronizacao entre o
 * `fetch()` do navegador (que setou o cookie) e o jar exposto via CDP pode ficar
 * uma volta de evento atras; sem esperar, `page.request.*` pode sair sem cookie e
 * o backend real responde 401 (sem sessao) em vez do 403/201 esperado pelo teste.
 */
async function loginViaTestHarness(page: Page, testId: string) {
  const responsePromise = page.waitForResponse(
    (r) => r.url().endsWith("/auth/session") && r.request().method() === "POST",
  );
  await page.getByTestId(testId).click();
  const response = await responsePromise;
  const status = response.status();
  const headers = response.headers();
  const body = (await response.json()) as {
    csrf_token: string;
    tenant_id: string;
    user_id: string;
  };
  await expect(async () => {
    const cookies = await page.context().cookies();
    expect(cookies.some((c) => c.name === "campaia_session")).toBe(true);
  }).toPass({ timeout: 5_000 });
  return { status, headers, body };
}

/**
 * FATO CONFIRMADO nesta sessao: `page.request` (APIRequestContext) NUNCA repassa o
 * cookie `campaia_session` setado por um `fetch()` feito pelo proprio script da
 * pagina (login real via AuthProvider) -- mesmo que `context.cookies()` (consulta
 * direta ao navegador via CDP) ja confirme o cookie presente. Isso e' uma limitacao
 * do cliente de teste (Playwright 1.63 + Chromium, cookie jar interno de
 * `page.request` nao observa `Set-Cookie` de fetches feitos pelo renderer), nunca
 * do backend real nem do AuthProvider -- o proprio navegador manda o cookie
 * corretamente em toda navegacao/fetch subsequente (ver rastreamento de rede real
 * confirmado manualmente). Por isso as chamadas de API deste harness anexam o
 * cookie explicitamente a partir de `context.cookies()`, em vez de depender da
 * propagacao implicita do `page.request`.
 */
async function sessionCookieHeader(page: Page): Promise<Record<string, string>> {
  const cookies = await page.context().cookies();
  const sessionCookie = cookies.find((c) => c.name === "campaia_session");
  if (!sessionCookie) return {};
  return { cookie: `campaia_session=${sessionCookie.value}` };
}

test.describe("Protocolo de sessao real", () => {
  test.beforeEach(async ({ context }) => {
    await context.clearCookies();
  });

  test("A. sem sessao -> /dashboard redireciona para /login", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login\?next=%2Fdashboard/);
  });

  test("B. login real via harness de teste -> POST /auth/session real -> dashboard", async ({
    page,
  }) => {
    await page.goto("/login");
    const { status } = await loginViaTestHarness(page, TENANT_A_TESTID);
    expect(status).toBe(200);
    // `headers()["set-cookie"]` nao esta disponivel via API JS do navegador
    // (restricao do proprio Chromium, nao um bug do backend) -- a confirmacao real
    // de que o cookie de sessao foi setado ja aconteceu dentro de
    // `loginViaTestHarness()`, via `context.cookies()`.
    const cookies = await page.context().cookies();
    expect(cookies.find((c) => c.name === "campaia_session")?.value).toBeTruthy();

    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByText("demo-tenant").first()).toBeVisible();
  });

  test("C. reload completo preserva a sessao e recupera o CSRF", async ({ page }) => {
    await page.goto("/login");
    await loginViaTestHarness(page, TENANT_A_TESTID);
    await expect(page).toHaveURL(/\/dashboard/);

    const sessionResponsePromise = page.waitForResponse((r) =>
      r.url().endsWith("/auth/session") && r.request().method() === "GET",
    );
    await page.reload();
    const sessionResponse = await sessionResponsePromise;
    expect(sessionResponse.status()).toBe(200);
    const body = await sessionResponse.json();
    expect(body.csrf_token).toBeTruthy();
    await expect(page.getByText("demo-tenant").first()).toBeVisible();
  });

  test("D. GET /me real devolve roles corretos", async ({ page }) => {
    await page.goto("/login");
    await loginViaTestHarness(page, TENANT_A_TESTID);
    await expect(page).toHaveURL(/\/dashboard/);

    const meResponse = await page.request.get("/api/campaia/me", {
      headers: await sessionCookieHeader(page),
    });
    expect(meResponse.status()).toBe(200);
    const me = await meResponse.json();
    expect(me.roles).toContain("OWNER");
  });

  test("E. mutacao sem CSRF e recusada pelo backend real", async ({ page }) => {
    await page.goto("/login");
    await loginViaTestHarness(page, TENANT_A_TESTID);
    await expect(page).toHaveURL(/\/dashboard/);

    const response = await page.request.post("/api/campaia/brand-profiles", {
      data: { name: "Sem CSRF", tone: "" },
      headers: {
        ...(await sessionCookieHeader(page)),
        "idempotency-key": "e2e-sem-csrf-0000000001",
      },
    });
    expect(response.status()).toBe(403);
  });

  test("F. mutacao com CSRF correto chega ao backend real", async ({ page }) => {
    await page.goto("/login");
    const { body: loginBody } = await loginViaTestHarness(page, TENANT_A_TESTID);
    await expect(page).toHaveURL(/\/dashboard/);

    const response = await page.request.post("/api/campaia/brand-profiles", {
      data: { name: "Com CSRF correto", tone: "" },
      headers: {
        ...(await sessionCookieHeader(page)),
        "x-csrf-token": loginBody.csrf_token,
        "idempotency-key": "e2e-com-csrf-0000000001",
      },
    });
    expect(response.status()).toBe(201);
  });

  test("G. logout invalida a sessao -- dashboard volta a exigir login", async ({ page }) => {
    await page.goto("/login");
    await loginViaTestHarness(page, TENANT_A_TESTID);
    await expect(page).toHaveURL(/\/dashboard/);

    await page.getByTestId("logout-button").click();
    await expect(page).toHaveURL(/\/login/);

    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });

  test("H. cookie invalido/adulterado falha fechado", async ({ page, context }) => {
    await context.addCookies([
      {
        name: "campaia_session",
        value: "cookie-adulterado-nao-existe-no-servidor",
        domain: "127.0.0.1",
        path: "/",
      },
    ]);
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });

  test("I. e-mail nao verificado e recusado, nunca autentica", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId(UNVERIFIED_TESTID).click();
    await expect(page.getByText(/Não foi possível entrar/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("I2. autenticado sem vinculo interno -> 403, nenhum autoprovisionamento", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.getByTestId(UNKNOWN_TESTID).click();
    await expect(page.getByText(/sem vínculo com nenhum tenant/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("J. cross-tenant: sessao do tenant A nunca ve dado do tenant B (OBRIGATORIO)", async ({
    browser,
  }) => {
    const contextA = await browser.newContext();
    const pageA = await contextA.newPage();
    await pageA.goto("/login");
    const { body: loginABody } = await loginViaTestHarness(pageA, TENANT_A_TESTID);
    await expect(pageA).toHaveURL(/\/dashboard/);
    await expect(pageA.getByText("demo-tenant").first()).toBeVisible();

    // Tenant A cria um brand profile real.
    const createResponse = await pageA.request.post("/api/campaia/brand-profiles", {
      data: { name: "Segredo do tenant A", tone: "" },
      headers: {
        ...(await sessionCookieHeader(pageA)),
        "x-csrf-token": loginABody.csrf_token,
        "idempotency-key": "e2e-cross-tenant-a-0000001",
      },
    });
    expect(createResponse.status()).toBe(201);

    // Sessao B, em contexto de navegador TOTALMENTE separado (cookies isolados).
    const contextB = await browser.newContext();
    const pageB = await contextB.newPage();
    await pageB.goto("/login");
    await loginViaTestHarness(pageB, TENANT_B_TESTID);
    await expect(pageB).toHaveURL(/\/dashboard/);
    await expect(pageB.getByText("other-tenant").first()).toBeVisible();

    // B nunca ve o brand profile de A -- tenant vem exclusivamente da sessao real,
    // nunca de header/body/query controlado pelo navegador.
    const listResponse = await pageB.request.get("/api/campaia/brand-profiles", {
      headers: await sessionCookieHeader(pageB),
    });
    expect(listResponse.status()).toBe(200);
    const brandProfilesForB = await listResponse.json();
    expect(brandProfilesForB).toEqual([]);

    // A UI de B tambem nunca renderiza qualquer texto do segredo de A.
    await expect(pageB.getByText("Segredo do tenant A", { exact: true })).toHaveCount(0);

    await contextA.close();
    await contextB.close();
  });

  test("K. troca real de tenant/unidade via UI (WP-03) -- backend valida, sessao real muda", async ({
    page,
  }) => {
    await page.goto("/login");
    await loginViaTestHarness(page, MULTI_TENANT_TESTID);
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByText("demo-tenant").first()).toBeVisible();

    await page.goto("/settings");
    await expect(page.getByText("Ativo")).toBeVisible();
    await expect(page.getByText("other-tenant")).toBeVisible();

    const switchResponsePromise = page.waitForResponse((r) =>
      r.url().endsWith("/auth/session/switch"),
    );
    await page.getByTestId("switch-membership-user-multi-1b").click();
    const switchResponse = await switchResponsePromise;
    expect(switchResponse.status()).toBe(200);
    expect((await switchResponse.json()).tenant_id).toBe("other-tenant");

    // A UI real reflete o novo tenant ativo sem precisar de novo login.
    await expect(page.getByText("other-tenant").first()).toBeVisible();

    // Backend real: /me da MESMA sessao agora resolve para o novo vinculo.
    const meResponse = await page.request.get("/api/campaia/me", {
      headers: await sessionCookieHeader(page),
    });
    expect((await meResponse.json()).tenant_id).toBe("other-tenant");
  });

  test("L. WP-04 real: Brand Kit e Conexao completos via UI, backend real", async ({ page }) => {
    await page.goto("/login");
    const { body: brandLoginBody } = await loginViaTestHarness(page, TENANT_A_TESTID);
    await expect(page).toHaveURL(/\/dashboard/);

    // Brand Kit: cria um real via UI, backend real persiste. Nao assume lista vazia --
    // outros testes deste mesmo arquivo ja podem ter criado brand-profiles para
    // demo-tenant no mesmo processo de backend (E2E nao reinicia o servidor por teste).
    await page.goto("/brand-kit");
    await page.getByLabel("Nome").fill("Marca E2E");
    await page.getByLabel("Tom de voz").fill("inspirador");
    await page.getByLabel(/Restrições de comunicação/).fill("Evite promessas de retorno garantido.");
    const createResponsePromise = page.waitForResponse(
      (r) => r.url().endsWith("/brand-profiles") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Salvar Brand Kit" }).click();
    const createResponse = await createResponsePromise;
    expect(createResponse.status()).toBe(201);
    const createdBrand = await createResponse.json();
    const brandCard = page.getByTestId('brand-profile-' + createdBrand.id);
    await expect(brandCard.getByText("Marca E2E", { exact: true })).toBeVisible();
    const second = await page.context().newPage();
    await second.goto("/brand-kit");
    await second.getByTestId('brand-profile-' + createdBrand.id).getByRole("button", { name: "Editar Marca E2E", exact: true }).click();
    await second.getByLabel("Tom de voz").fill("rascunho concorrente");
    await brandCard.getByRole("button", { name: "Editar Marca E2E", exact: true }).click();
    await page.getByLabel("Tom de voz").fill("direto");
    const updatePromise = page.waitForResponse(response =>
      response.url().endsWith('/brand-profiles/' + createdBrand.id) && response.request().method() === 'PUT');
    await page.getByRole("button", { name: "Salvar alterações", exact: true }).click();
    const updateResponse = await updatePromise;
    expect(updateResponse.status()).toBe(200);
    expect((await updateResponse.json()).version).toBe(2);
    await expect(brandCard.getByText("direto", { exact: true })).toBeVisible();
    const conflictPromise = second.waitForResponse(response =>
      response.url().endsWith('/brand-profiles/' + createdBrand.id) && response.request().method() === 'PUT');
    await second.getByRole("button", { name: "Salvar alterações", exact: true }).click();
    const conflict = await conflictPromise;
    expect(conflict.status()).toBe(409);
    expect((await conflict.json()).code).toBe("BRAND_VERSION_CHANGED");
    await expect(second.getByLabel("Tom de voz")).toHaveValue("rascunho concorrente");
    await second.close();
    await brandCard.getByRole("button", { name: "Histórico de Marca E2E", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Versão 2 — Marca E2E", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Versão 1 — Marca E2E", exact: true })).toBeVisible();
    const historyResponse = await page.request.get('/api/campaia/brand-profiles/' + createdBrand.id + '/versions',
      { headers: await sessionCookieHeader(page) });
    expect(historyResponse.status()).toBe(200);
    const history = await historyResponse.json();
    expect(history.items.map((item: { version: number }) => item.version)).toEqual([2, 1]);
    expect(history.items[1].tone).toBe("inspirador");


    // Assets: API + SQLite + worker reais; armazenamento de objetos explicitamente simulado.
    await brandCard.getByRole("button", { name: "Arquivos de Marca E2E", exact: true }).click();
    const assetsPanel = page.getByRole("region", { name: "Arquivos de Marca E2E", exact: true });
    await expect(assetsPanel.getByText("Ambiente de teste: armazenamento simulado.")).toBeVisible();
    await assetsPanel.getByLabel("Imagem da marca").setInputFiles({
      name: "logo.png", mimeType: "image/png", buffer: smallStaticPng(),
    });
    const uploadPromise = page.waitForResponse(response => response.url().includes('/brand-profiles/' + createdBrand.id + '/assets?kind=LOGO')
      && response.request().method() === 'POST');
    await assetsPanel.getByRole("button", { name: "Enviar imagem", exact: true }).click();
    const uploadResponse = await uploadPromise;
    expect(uploadResponse.status()).toBe(201);
    const uploaded = await uploadResponse.json();
    expect(uploaded.status).toBe("READY");
    const preview = assetsPanel.getByRole("img", { name: "Logo de Marca E2E", exact: true });
    await expect(preview).toBeVisible();
    await expect.poll(() => preview.evaluate(image => (image as HTMLImageElement).naturalWidth)).toBe(2);

    const contextAssetB = await page.context().browser()!.newContext();
    const pageAssetB = await contextAssetB.newPage();
    await pageAssetB.goto("/login");
    await loginViaTestHarness(pageAssetB, TENANT_B_TESTID);
    const foreign = await pageAssetB.request.get(uploaded.content_url, { headers: await sessionCookieHeader(pageAssetB) });
    expect(foreign.status()).toBe(404);
    await contextAssetB.close();


    const briefPage = await page.context().newPage();
    await briefPage.goto("/campaigns");
    await briefPage.getByRole("button", { name: "Escolher Brand Kit", exact: true }).click();
    await expect(briefPage.getByRole("option", { name: "Marca E2E · versão 2", exact: true }).last()).toBeAttached();
    await briefPage.getByLabel("Brand Kit da campanha").selectOption(createdBrand.id);
    await briefPage.getByRole("checkbox").check();
    await briefPage.getByLabel("Objetivo", { exact: true }).fill("Campanha com marca registrada E2E");
    const briefPromise = briefPage.waitForResponse(response => response.url().endsWith("/briefs") && response.request().method() === "POST");
    await briefPage.getByRole("button", { name: "Enviar briefing", exact: true }).click();
    const briefResponse = await briefPromise;
    expect(briefResponse.status()).toBe(202);
    const brandedCampaign = await briefResponse.json();
    expect(brandedCampaign.brief.brand_snapshot_v1.profile.version).toBe(2);
    expect(brandedCampaign.brief.brand_snapshot_v1.assets.map((asset: { id: string }) => asset.id)).toEqual([uploaded.id]);
    const changedBrand = await page.request.put('/api/campaia/brand-profiles/' + createdBrand.id, {
      headers: { ...(await sessionCookieHeader(page)), "x-csrf-token": brandLoginBody.csrf_token,
        "idempotency-key": "e2e-brand-edit-after-brief-" + createdBrand.id },
      data: { name: createdBrand.name, tone: "editado depois do briefing", colors: [],
        differentiators: [], restrictions: ["Evite promessas de retorno garantido."], expected_version: 2 },
    });
    expect(changedBrand.status()).toBe(200);
    await briefPage.goto('/campaigns/' + brandedCampaign.id);
    const frozenBrand = briefPage.getByRole("region", { name: "Marca registrada nesta campanha" });
    await expect(frozenBrand.getByText("Marca E2E · versão 2", { exact: true })).toBeVisible();
    await expect(frozenBrand.getByText("Tom de voz: direto", { exact: true })).toBeVisible();
    await expect(frozenBrand.getByText("Evite promessas de retorno garantido.", { exact: true })).toBeVisible();
    const strategyPromise = briefPage.waitForResponse(response => response.url().endsWith("/plan/regenerate") && response.request().method() === "POST");
    await briefPage.getByRole("button", { name: "Gerar estratégia", exact: true }).click();
    expect((await strategyPromise).status()).toBe(202);
    const policyPromise = briefPage.waitForResponse(response => response.url().endsWith("/validate") && response.request().method() === "POST");
    await briefPage.getByRole("button", { name: "Validar campanha", exact: true }).click();
    const brandDecision = await (await policyPromise).json();
    expect(brandDecision.requires_human_approval).toBe(true);
    expect(brandDecision.findings.map((finding: { code: string }) => finding.code)).toContain("BRAND_GUIDANCE_REVIEW_REQUIRED");
    await briefPage.close();

    const assetUrl = '/api/campaia/brand-profiles/' + createdBrand.id + '/assets/' + uploaded.id;
    const withoutCsrf = await page.request.delete(assetUrl, {
      headers: { ...(await sessionCookieHeader(page)), "idempotency-key": "e2e-asset-no-csrf-0001" },
    });
    expect(withoutCsrf.status()).toBe(403);
    await assetsPanel.getByRole("button", { name: "Remover imagem", exact: true }).click();
    const deletePromise = page.waitForResponse(response => response.url().endsWith('/assets/' + uploaded.id)
      && response.request().method() === 'DELETE');
    await assetsPanel.getByRole("button", { name: "Confirmar remoção", exact: true }).click();
    expect((await deletePromise).status()).toBe(200);
    await expect(assetsPanel.getByText("Nenhum arquivo registrado.")).toBeVisible();
    const removed = await page.request.get(uploaded.content_url, { headers: await sessionCookieHeader(page) });
    expect(removed.status()).toBe(404);
    const blockedStrategy = await page.request.post('/api/campaia/campaigns/' + brandedCampaign.id + '/plan/regenerate', {
      headers: { ...(await sessionCookieHeader(page)), "x-csrf-token": brandLoginBody.csrf_token,
        "idempotency-key": "e2e-brand-removed-plan-" + brandedCampaign.id }, data: {},
    });
    expect(blockedStrategy.status()).toBe(409);
    expect((await blockedStrategy.json()).code).toBe("BRAND_ASSET_UNAVAILABLE");


    // Conexoes: fecha o ciclo real start -> callback -> Connection persistida.
    await page.goto("/connections");
    await expect(page.getByTestId("connect-GOOGLE_ADS")).toBeVisible();
    await page.getByTestId("connect-GOOGLE_ADS").click();
    await expect(page.getByText(/esta ação exige reautenticação recente/i)).toBeVisible();

    const startResponsePromise = page.waitForResponse((r) =>
      r.url().endsWith("/connections/oauth/start"),
    );
    await page.getByRole("button", { name: "Confirmar e conectar" }).click();
    const startResponse = await startResponsePromise;
    expect(startResponse.status()).toBe(200);

    await expect(page.getByTestId("complete-connection-GOOGLE_ADS")).toBeVisible();
    await page.getByLabel("ID da conta").fill("acct-e2e-real");
    await page.getByLabel("Nome de exibição").fill("Conta E2E Real");

    const callbackResponsePromise = page.waitForResponse((r) =>
      r.url().endsWith("/connections/oauth/callback"),
    );
    await page.getByTestId("complete-connection-GOOGLE_ADS").click();
    const callbackResponse = await callbackResponsePromise;
    expect(callbackResponse.status()).toBe(201);
    await expect(page.getByText(/conectado — conta e2e real/i)).toBeVisible();

    // Backend real: a Connection de fato existe, nao so na UI otimista.
    const listResponse = await page.request.get("/api/campaia/connections", {
      headers: await sessionCookieHeader(page),
    });
    const connections = await listResponse.json();
    expect(connections).toHaveLength(1);
    expect(connections[0].external_account_id).toBe("acct-e2e-real");
  });

  test("M. WP-05 real: briefing -> estrategia -> validacao -> pedido de aprovacao via UI, segregacao de funcoes real no backend", async ({
    page,
  }) => {
    await page.goto("/login");
    const { body: loginBody } = await loginViaTestHarness(page, TENANT_A_TESTID);
    await expect(page).toHaveURL(/\/dashboard/);

    await page.goto("/campaigns");
    await page.getByLabel("Objetivo").fill("Campanha E2E WP-05");
    const briefResponsePromise = page.waitForResponse(
      (r) => r.url().endsWith("/briefs") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Enviar briefing" }).click();
    const briefResponse = await briefResponsePromise;
    expect(briefResponse.status()).toBe(202);
    const campaign = await briefResponse.json();

    await page.getByText("Campanha E2E WP-05").click();
    await expect(page).toHaveURL(new RegExp(`/campaigns/${campaign.id}$`));

    const planResponsePromise = page.waitForResponse(
      (r) => r.url().endsWith("/plan/regenerate") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Gerar estratégia" }).click();
    expect((await planResponsePromise).status()).toBe(202);
    await expect(page.getByText(/"objetivo"/)).toBeVisible();

    const validateResponsePromise = page.waitForResponse((r) =>
      r.url().endsWith("/validate"),
    );
    await page.getByRole("button", { name: "Validar campanha" }).click();
    const validateResponse = await validateResponsePromise;
    expect(validateResponse.status()).toBe(200);
    const decision = await validateResponse.json();
    expect(decision.outcome).toBe("APPROVABLE");
    await expect(page.getByText(/resultado: approvable/i)).toBeVisible();

    const approvalResponsePromise = page.waitForResponse(
      (r) => r.url().endsWith("/approvals") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Solicitar aprovação para publicar" }).click();
    const approvalResponse = await approvalResponsePromise;
    expect(approvalResponse.status()).toBe(201);
    const approval = await approvalResponse.json();
    expect(approval.status).toBe("PENDING");

    // Segregacao de funcoes real (I-09/campaia_core.permissions.can_approve): quem
    // propos (owner@demo-tenant, o mesmo user_id desta sessao) NUNCA pode aprovar a
    // propria proposta, mesmo tendo APPROVAL_DECIDE -- backend real recusa, nunca a UI.
    const selfApproveResponse = await page.request.post(
      `/api/campaia/approvals/${approval.id}/decision`,
      {
        data: { decision: "APPROVE" },
        headers: {
          ...(await sessionCookieHeader(page)),
          "x-csrf-token": loginBody.csrf_token,
          "x-step-up-token": "e2e-self-approve-attempt",
          "idempotency-key": "e2e-self-approve-attempt-0000001",
        },
      },
    );
    expect(selfApproveResponse.status()).toBe(403);
    expect((await selfApproveResponse.json()).code).toBe("SEPARATION_OF_DUTIES");

    // Fila de aprovacoes real reflete o pedido pendente.
    await page.goto("/approvals");
    await expect(page.getByText(new RegExp(campaign.id))).toBeVisible();
  });
});
