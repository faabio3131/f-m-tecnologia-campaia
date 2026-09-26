import { defineConfig, devices } from "@playwright/test";

/**
 * E2E real do protocolo de sessao (Etapa 2, secao 29-30) -- Playwright real contra
 * o Next.js real (build de producao real, `next build` + `next start`) + o backend
 * Starlette real (harness de E2E, backend/tests_support/e2e_server.py), nunca um
 * mock de rede.
 *
 * FATO CONFIRMADO nesta sessao: `next dev` (Turbopack) neste ambiente sandboxed tem
 * o handshake do WebSocket de HMR (`ws://.../_next/hmr`) falhando
 * (`net::ERR_INVALID_HTTP_RESPONSE`), o que impede a hidratacao do React no cliente
 * por completo -- nenhum efeito roda, nenhum fetch e disparado, a UI trava
 * permanentemente no estado inicial de SSR ("Verificando sessão"). Isso NAO e uma
 * regressao do AuthProvider/guard: sob `next build` + `next start` (producao), a
 * mesma UI hidrata e o bootstrap real (`GET /auth/session`) roda corretamente.
 * Por isso este harness builda com `NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE=test` (que so
 * pode ser lido em build time, nunca em runtime, ja que e inlined no bundle) antes
 * de iniciar o servidor de producao -- nunca usa `next dev` aqui.
 *
 * Config separada do `playwright.config.ts` (smoke do WP-01, sem login, build de
 * producao) de proposito: aqui SEMPRE roda em modo de teste explicito, nunca contra
 * o build de producao real usado pelo publico final (que nunca tem
 * NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE=test).
 */
const WEB_PORT = 4174;
const BACKEND_PORT = 8099;
const WEB_ORIGIN = `http://127.0.0.1:${WEB_PORT}`;
const BACKEND_ORIGIN = `http://127.0.0.1:${BACKEND_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  testMatch: /session-protocol\.spec\.ts/,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  timeout: 30_000,
  use: {
    baseURL: WEB_ORIGIN,
    trace: "retain-on-failure",
    launchOptions: {
      executablePath: process.env.CAMPAIA_CHROMIUM_PATH,
    },
  },
  webServer: [
    {
      command: `python3 -m tests_support.e2e_server`,
      cwd: "../backend",
      url: `${BACKEND_ORIGIN}/auth/session`,
      // GET /auth/session sem cookie responde 401 -- o servidor esta de pe, mesmo
      // que o endpoint em si "falhe". Playwright so precisa que a porta responda.
      reuseExistingServer: false,
      timeout: 30_000,
      env: {
        CAMPAIA_E2E_ALLOWED_ORIGIN: WEB_ORIGIN,
        CAMPAIA_E2E_PORT: String(BACKEND_PORT),
      },
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      // `next build` (nao `next dev`) -- ver comentario do arquivo. O build
      // inlina NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE=test; o `next start` resultante
      // serve exatamente esse build, nunca modo de desenvolvimento.
      command: `npm run build && npm run start -- --port ${WEB_PORT}`,
      url: WEB_ORIGIN,
      reuseExistingServer: false,
      timeout: 180_000,
      env: {
        CAMPAIA_BFF_ORIGIN: BACKEND_ORIGIN,
        NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE: "test",
      },
    },
  ],
  projects: [
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
