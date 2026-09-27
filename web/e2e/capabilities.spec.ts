import { test, expect, type Page } from "@playwright/test";

/**
 * E2E cross-stack REAL do WP-09 (capacidades de conexão) -- reconciliação PR#6,
 * 26/09/2026, ATUALIZADO na Fase 3 (achado 20, 26/09/2026).
 *
 * HISTÓRICO (WP-09, achado original): `CapabilityRegistry` (`campaia_core/infra.py`) é
 * indexado por `(provider, capability_key, country, api_version)`;
 * `api/state.py::_seed_capabilities()` só registra capacidades sob `provider="SIMULATOR"`.
 * `GET /connections/{id}/capabilities` consultava esse registro com `conn.provider` --
 * o RÓTULO da conta OAuth (`GOOGLE_ADS`/`META`/`WHATSAPP`, contrato `Provider`), que
 * nunca bate com `"SIMULATOR"` -- e por isso sempre devolvia `supported: false` para
 * qualquer conta real, com um `verified_at` fabricado (`datetime.now()`) para disfarçar.
 * Esse comportamento foi documentado no WP-09 como "honesto por acidente" e deixado como
 * estava.
 *
 * ACHADO 20 (Fase 3, reinvestigação com execução real): isso não era honestidade
 * deliberada -- era um descasamento de indexação genuíno. `routes_campaigns.py::
 * validate_campaign` já consulta o MESMO registro com o literal `"SIMULATOR"`
 * (independente da conta OAuth) para decidir se uma campanha pode publicar de verdade --
 * e publica com sucesso via `POST /campaigns/{id}/publish` nos specs
 * `session-protocol.spec.ts` (teste M) e nos testes de invariantes do backend. As duas
 * rotas respondiam perguntas inconsistentes sobre o MESMO fato real. Corrigido mapeando
 * `conn.mode` (`ConnectionMode`, o eixo real de execução -- toda conexão hoje é
 * `SIMULATOR`, não existe adaptador real para nenhum provider ainda) para a chave real do
 * registro, em vez do rótulo da conta OAuth. `supported: true` aqui NUNCA afirma
 * homologação externa real (Google Ads/Meta/WhatsApp continuam "NÃO VERIFICADO" no
 * Capability Matrix histórico, docs/08_CAPABILITY_MATRIX.md da PR#6) -- só que a
 * plataforma sabe executar a ação hoje via simulador, disclosurado explicitamente pelo
 * próprio `notes` do registro ("Simulated capability, verified in-process at startup.").
 * Um modo de conexão sem adaptador real seedado (TEST/PRODUCTION, nenhum hoje) continua
 * honestamente `supported: false`/`verified_at: null` -- nunca fabricado.
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
  test("mostra as capacidades reais de uma conexão recém-criada, consistentes com o que a plataforma de fato executa", async ({
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
      verified_at: string | null;
      notes: string | null;
    }[];

    expect(capabilities.length).toBeGreaterThan(0);
    // ACHADO 20: uma conexão recém-criada é SIMULATOR por padrão (nenhum adaptador real
    // de execução existe ainda para nenhum provider) -- a plataforma sabe executar
    // PUBLISH via simulador hoje, e isso é o que `supported: true` significa aqui, nunca
    // homologação externa real.
    expect(capabilities.every((c) => c.supported === true)).toBe(true);
    expect(capabilities.every((c) => c.evidence_url === null)).toBe(true);
    expect(capabilities.every((c) => c.verified_at !== null)).toBe(true);
    // O disclosure honesto de que isto é simulado, não uma integração real verificada,
    // vem do próprio registro -- nunca escondido nem apresentado como homologação real.
    expect(capabilities.every((c) => (c.notes ?? "").includes("Simulated"))).toBe(true);

    await expect(page.getByText("PUBLISH:GOOGLE_ADS")).toBeVisible();
    await expect(page.getByText("Suportada").first()).toBeVisible();
    await expect(page.getByText(/sem evidência registrada/i).first()).toBeVisible();
    await expect(page.getByText(/Simulated capability/i).first()).toBeVisible();
  });
});
