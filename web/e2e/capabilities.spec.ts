import { test, expect, type Page } from "@playwright/test";

/**
 * E2E cross-stack REAL do WP-09 (capacidades de conexão) -- reconciliação PR#6,
 * 26/09/2026. Roda contra o mesmo harness real já usado pelos outros specs desta
 * reconciliação (backend Starlette real + Next.js real em build de produção, ver
 * playwright.session.config.ts), nunca um mock de rede.
 *
 * ACHADO REAL confirmado por execução direta nesta sessão (não por leitura de código
 * apenas): `campaia_core/infra.py::CapabilityRegistry` é indexado por
 * `(provider, capability_key, country, api_version)`; `api/state.py::_seed_capabilities()`
 * só registra capacidades sob `provider="SIMULATOR"`, mas nenhuma `Connection` real criada
 * pelo fluxo de OAuth (`routes_connections.py::oauth_callback`) jamais tem esse provider
 * -- o `Provider` do contrato é `GOOGLE_ADS | META | WHATSAPP`. Isso significa que
 * `GET /connections/{id}/capabilities` hoje SEMPRE devolve `supported: false` para
 * qualquer conexão real, para as duas chaves testadas (`PUBLISH:GOOGLE_ADS`,
 * `PUBLISH:META_ADS`).
 *
 * Decisão registrada nesta reconciliação: NÃO alterado. `"SIMULATOR"` também é usado
 * deliberadamente em `routes_campaigns.py::validate_campaign` como o publicador
 * simulado da PLATAFORMA (independente da conta OAuth escolhida) -- mudar o seed para
 * "provar" capacidades de contas reais fabricaria um `supported: true` que nunca foi de
 * fato verificado para nenhuma conta real, contrariando a mesma disciplina de honestidade
 * já aplicada a `insights` (nunca fabricar métricas) e ao Gemini/IA (nunca inventar
 * verificação). Por isso este E2E verifica exatamente o comportamento real e honesto --
 * nenhuma capacidade aparece como suportada até existir verificação real de conta --, não
 * um resultado "feliz" fabricado. Ver evidência completa no doc desta reconciliação.
 *
 * Usa o tenant B (não o A): `session-protocol.spec.ts`'s teste L já conecta GOOGLE_ADS
 * para o tenant A nesta mesma suíte (harness real, backend persistente durante toda a
 * execução) -- criar aqui uma segunda conexão GOOGLE_ADS para o tenant A quebraria a
 * suposição daquele teste de que o botão "Conectar" ainda está disponível.
 */

const TENANT_B_TESTID = "test-identity-e2e-test-id-token-tenant-b-owner";

async function loginViaTestHarness(page: Page, testId: string) {
  const responsePromise = page.waitForResponse(
    (r) => r.url().endsWith("/auth/session") && r.request().method() === "POST",
  );
  await page.getByTestId(testId).click();
  await responsePromise;
  await expect(async () => {
    const cookies = await page.context().cookies();
    expect(cookies.some((c) => c.name === "campaia_session")).toBe(true);
  }).toPass({ timeout: 5_000 });
}

test.describe("WP-09: capacidades de conexão cross-stack", () => {
  test("mostra as capacidades reais de uma conexão recém-criada, honestamente não suportadas", async ({
    page,
  }) => {
    await page.goto("/login");
    await loginViaTestHarness(page, TENANT_B_TESTID);
    await expect(page).toHaveURL(/\/dashboard/);

    // Fecha o ciclo real de conexao (mesmo fluxo do teste L de session-protocol.spec.ts)
    // para ter uma Connection real, persistida pelo backend, antes de checar capacidades.
    await page.goto("/connections");
    const label = `WP-09 E2E ${Date.now()}`;
    const connectButton = page.getByTestId("connect-GOOGLE_ADS");
    const alreadyConnectedText = page.getByText(/conectado —/i).first();
    // Espera de verdade o carregamento real (GET /connections) assentar antes de decidir
    // entre os dois estados possiveis -- nao confia em isVisible()/count() imediatos, que
    // nao esperam a resposta real do backend chegar e a UI re-renderizar.
    await expect(connectButton.or(alreadyConnectedText)).toBeVisible();
    if (await connectButton.isVisible()) {
      await page.getByTestId("connect-GOOGLE_ADS").click();
      const startResponsePromise = page.waitForResponse((r) =>
        r.url().endsWith("/connections/oauth/start"),
      );
      await page.getByRole("button", { name: "Confirmar e conectar" }).click();
      const startResponse = await startResponsePromise;
      expect(startResponse.status()).toBe(200);
      await page.getByLabel("ID da conta").fill(`acct-${label}`);
      await page.getByLabel("Nome de exibição").fill(label);
      const callbackResponsePromise = page.waitForResponse((r) =>
        r.url().endsWith("/connections/oauth/callback"),
      );
      await page.getByTestId("complete-connection-GOOGLE_ADS").click();
      const callbackResponse = await callbackResponsePromise;
      expect(callbackResponse.status()).toBe(201);
    }

    await expect(page.getByText(/conectado —/i).first()).toBeVisible();

    const toggle = page.getByTestId(/^toggle-capabilities-/).first();
    const capabilitiesResponse = page.waitForResponse(
      (r) => r.url().includes("/capabilities") && r.request().method() === "GET",
    );
    await toggle.click();
    const response = await capabilitiesResponse;
    expect(response.status()).toBe(200);
    const capabilities = (await response.json()) as {
      capability_key: string;
      supported: boolean;
      evidence_url: string | null;
    }[];

    expect(capabilities.length).toBeGreaterThan(0);
    // Comportamento real e honesto (ver nota do arquivo): nenhuma capacidade de uma
    // conta recem-conectada e reportada como suportada sem verificacao real.
    expect(capabilities.every((c) => c.supported === false)).toBe(true);
    expect(capabilities.every((c) => c.evidence_url === null)).toBe(true);

    await expect(page.getByText("PUBLISH:GOOGLE_ADS")).toBeVisible();
    await expect(page.getByText("Não suportada").first()).toBeVisible();
    await expect(page.getByText(/sem evidência registrada/i).first()).toBeVisible();
  });
});
