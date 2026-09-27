import { test, expect, type Page } from "@playwright/test";

/**
 * ACHADO 21 (Fase 3 da missão de reconciliação/takeover, item 3, 26/09/2026): E2E
 * cross-stack REAL certificando a paginação real de `GET /audit-events` na tela `/audit`
 * (WP-10) -- backend Starlette real + Next.js real (build de produção), sem mock de rede.
 *
 * HISTÓRICO: `next_cursor` era sempre `null` (achado 3/15 original) -- a Web nunca
 * mostrava nenhum controle de paginação porque o backend honestamente não tinha nada
 * para paginar. Corrigido nesta Fase 3 (achado 21): o backend agora implementa
 * paginação real por cursor opaco (página fixa de 50), e a tela `/audit` segue esse
 * `next_cursor` real com um botão "Carregar mais".
 *
 * Usa o tenant B (não o A): `audit-trail.spec.ts` e `kill-switch.spec.ts` já fazem
 * asserções sobre `GET /audit-events` SEM cursor para o tenant A nesta mesma suíte
 * (backend persistente durante toda a execução) -- criar aqui mais de 50 eventos reais
 * para o tenant A empurraria os eventos deles para além da primeira página e quebraria
 * essas asserções pré-existentes. O tenant B não é usado por nenhum outro spec desta
 * suíte para checar `/audit-events`.
 */

const TENANT_B_TESTID = "test-identity-e2e-test-id-token-tenant-b-owner";

async function loginViaTestHarness(page: Page, testId: string) {
  const responsePromise = page.waitForResponse(
    (r) => r.url().endsWith("/auth/session") && r.request().method() === "POST",
  );
  await page.getByTestId(testId).click();
  const response = await responsePromise;
  const body = (await response.json()) as { csrf_token: string };
  await expect(async () => {
    const cookies = await page.context().cookies();
    expect(cookies.some((c) => c.name === "campaia_session")).toBe(true);
  }).toPass({ timeout: 5_000 });
  return { csrfToken: body.csrf_token };
}

async function sessionCookieHeader(page: Page): Promise<Record<string, string>> {
  const cookies = await page.context().cookies();
  const sessionCookie = cookies.find((c) => c.name === "campaia_session");
  return sessionCookie ? { cookie: `campaia_session=${sessionCookie.value}` } : {};
}

interface AuditEventLite {
  id: string;
  action: string;
}

test.describe("WP-Fase3 achado 21: paginação real da trilha de auditoria cross-stack", () => {
  test("mais de uma página de eventos reais: 'Carregar mais' aparece, funciona, e não fabrica nem perde eventos", async ({
    page,
  }) => {
    test.setTimeout(60_000);
    await page.goto("/login");
    const { csrfToken } = await loginViaTestHarness(page, TENANT_B_TESTID);
    await expect(page).toHaveURL(/\/dashboard/);

    const headers = {
      ...(await sessionCookieHeader(page)),
      "x-csrf-token": csrfToken,
    };

    // Gera eventos reais suficientes para forçar mais de uma página (backend real,
    // pagina fixa de 50 -- ver api/routes_audit.py::_PAGE_SIZE).
    const total = 55;
    for (let i = 0; i < total; i += 1) {
      const r = await page.request.post("/api/campaia/briefs", {
        headers: { ...headers, "idempotency-key": `e2e-achado21-${i}-${Date.now()}`.padEnd(16, "x") },
        data: { objective: `WP-Fase3 achado21 ${i} ${Date.now()}` },
      });
      expect(r.status()).toBe(202);
    }

    // Página 1, direto contra o backend real (sem passar pela UI) -- confirma o
    // comportamento do endpoint isoladamente antes de exercitar a tela.
    const firstPage = await page.request.get("/api/campaia/audit-events", { headers });
    expect(firstPage.status()).toBe(200);
    const firstBody = (await firstPage.json()) as { items: AuditEventLite[]; next_cursor: string | null };
    expect(firstBody.items.length).toBe(50);
    expect(firstBody.next_cursor).not.toBeNull();

    const seenIds = new Set(firstBody.items.map((e) => e.id));
    let cursor = firstBody.next_cursor;
    let pagesWalked = 1;
    while (cursor) {
      const r = await page.request.get(`/api/campaia/audit-events?cursor=${cursor}`, { headers });
      expect(r.status()).toBe(200);
      const body = (await r.json()) as { items: AuditEventLite[]; next_cursor: string | null };
      for (const item of body.items) {
        expect(seenIds.has(item.id)).toBe(false); // nenhuma duplicata entre páginas
        seenIds.add(item.id);
      }
      cursor = body.next_cursor;
      pagesWalked += 1;
    }
    expect(pagesWalked).toBeGreaterThan(1);
    // Todos os eventos coletados sao CAMPAIGN_CREATE deste teste (tenant B isolado,
    // nenhum outro spec desta suite gera evento para ele antes deste ponto na ordem de
    // execucao) -- pelo menos `total`, sem lacunas nem duplicatas atraves das paginas.
    const campaignCreateCount = [...seenIds].length;
    expect(campaignCreateCount).toBeGreaterThanOrEqual(total);

    // Cursor desconhecido falha fechado, nunca reinicia silenciosamente a paginação.
    const badCursor = await page.request.get(
      "/api/campaia/audit-events?cursor=audit_999999_deadbeef",
      { headers },
    );
    expect(badCursor.status()).toBe(422);
    expect((await badCursor.json()).code).toBe("VALIDATION_FAILED");

    // Agora a tela real: "Carregar mais" aparece, funciona, e ao final some -- provando
    // que a Web segue o next_cursor real em vez de fabricar (ou ignorar) paginação.
    await page.goto("/audit");
    await expect(page.getByRole("button", { name: /carregar mais/i })).toBeVisible();

    let clicks = 0;
    while (await page.getByRole("button", { name: /carregar mais/i }).isVisible()) {
      clicks += 1;
      if (clicks > 5) throw new Error("Muitos cliques em 'Carregar mais' -- paginação não converge.");
      const nextResponse = page.waitForResponse(
        (r) => r.url().includes("/audit-events") && r.url().includes("cursor="),
      );
      await page.getByRole("button", { name: /carregar mais/i }).click();
      expect((await nextResponse).status()).toBe(200);
    }
    await expect(page.getByRole("button", { name: /carregar mais/i })).not.toBeVisible();

    // Todos os eventos reais coletados via cursor acima também aparecem na tela após
    // esgotar "Carregar mais" -- nenhum perdido pela paginação real na Web.
    await expect(async () => {
      const visibleCount = await page.getByText("CAMPAIGN_CREATE").count();
      expect(visibleCount).toBe(campaignCreateCount);
    }).toPass({ timeout: 5_000 });
  });
});
