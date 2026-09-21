import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { defineConfig, devices } from "@playwright/test";

/**
 * WP-03 cross-stack E2E: real backend (uvicorn, real OIDC test identity provider) + real
 * Next.js frontend, both over HTTPS on 127.0.0.1. Deliberately a SEPARATE config from
 * playwright.config.ts (WP-01/02's no-backend smoke config, unchanged) -- these tests need
 * a live backend and a build with NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN set, neither of which the
 * default config provides, and this file's testDir (./e2e-crossstack) is never picked up
 * by `npm run test:e2e`'s default config.
 *
 * HTTPS, not HTTP: WP-02's session cookie is `Secure` by design (never weakened, even for
 * tests -- see tests_api/test_auth_session.py's own https://testserver TestClient base_url
 * for the same principle at the HTTP-integration level). A browser silently drops Secure
 * cookies over plain http://, so a real login exercised through an actual browser needs a
 * real (if self-signed, locally-generated, gitignored *.pem, never committed) HTTPS origin
 * for both the frontend and the backend -- not a workaround that relaxes the cookie.
 */
const CERT_DIR = join(__dirname, "e2e-crossstack", ".certs");
const KEY_PATH = join(CERT_DIR, "key.pem");
const CERT_PATH = join(CERT_DIR, "cert.pem");

if (!existsSync(CERT_PATH) || !existsSync(KEY_PATH)) {
  mkdirSync(CERT_DIR, { recursive: true });
  execFileSync("openssl", [
    "req",
    "-x509",
    "-newkey",
    "rsa:2048",
    "-keyout",
    KEY_PATH,
    "-out",
    CERT_PATH,
    "-days",
    "1",
    "-nodes",
    "-subj",
    "/CN=127.0.0.1",
    "-addext",
    "subjectAltName=IP:127.0.0.1",
  ]);
}

const FRONTEND_PORT = 4174;
const BACKEND_PORT = 8443;
const BACKEND_ORIGIN = `https://127.0.0.1:${BACKEND_PORT}`;
const FRONTEND_ORIGIN = `https://127.0.0.1:${FRONTEND_PORT}`;

export default defineConfig({
  testDir: "./e2e-crossstack",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: `https://127.0.0.1:${FRONTEND_PORT}`,
    ignoreHTTPSErrors: true,
    trace: "retain-on-failure",
    launchOptions: {
      executablePath: process.env.CAMPAIA_CHROMIUM_PATH,
    },
  },
  webServer: [
    {
      // CAMPAIA_ENABLE_TEST_AUTH_FIXTURES + CAMPAIA_ENV=test: the same two-signal
      // fail-closed gate as every other test-only use of the identity provider
      // (backend/api/state.py AppState.__post_init__) -- neither alone is enough.
      // CAMPAIA_WEB_ORIGIN: the frontend and backend are different origins here (real
      // ports on 127.0.0.1), exactly like the production topology README.md documents --
      // without it, /auth/callback and /auth/logout would redirect the browser back to
      // THIS backend's own origin, which has no route to serve (see routes_auth.py's
      // _frontend_url).
      command:
        `CAMPAIA_ENV=test CAMPAIA_ENABLE_TEST_AUTH_FIXTURES=1 CAMPAIA_WEB_ORIGIN=${FRONTEND_ORIGIN} python3 -m uvicorn api.main:app ` +
        `--host 127.0.0.1 --port ${BACKEND_PORT} --ssl-keyfile ${KEY_PATH} --ssl-certfile ${CERT_PATH}`,
      cwd: "../backend",
      url: `${BACKEND_ORIGIN}/test-idp/.well-known/openid-configuration`,
      ignoreHTTPSErrors: true,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      // NODE_TLS_REJECT_UNAUTHORIZED=0: session.ts's GET /me and GET /session/memberships
      // fetches run server-side, in THIS Node process, against the backend's self-signed
      // HTTPS cert -- Node's own fetch validates TLS independently of the browser (which
      // trusts it via Playwright's ignoreHTTPSErrors above). NODE_EXTRA_CA_CERTS (trusting
      // our one generated cert specifically, without disabling verification) was tried
      // first and does NOT work here -- Next 16's Turbopack dev server's fetch
      // implementation does not pick it up, confirmed by reproducing the failure with it
      // set. This is scoped to this one E2E-only dev-server process (never product code,
      // never a deployed environment, never committed as a default) -- not a weakening of
      // any real TLS check, since a real provider is never self-signed.
      command:
        `NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN=${BACKEND_ORIGIN} NODE_TLS_REJECT_UNAUTHORIZED=0 ` +
        `npm run dev -- --port ${FRONTEND_PORT} ` +
        `--experimental-https --experimental-https-key ${KEY_PATH} --experimental-https-cert ${CERT_PATH}`,
      url: `https://127.0.0.1:${FRONTEND_PORT}`,
      ignoreHTTPSErrors: true,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
  projects: [
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
