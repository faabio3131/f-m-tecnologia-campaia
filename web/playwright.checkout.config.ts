import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e", testMatch: /billing-checkout\.spec\.ts/, fullyParallel: false,
  forbidOnly: !!process.env.CI, retries: 0, reporter: [["list"]], timeout: 30_000,
  use: { baseURL: "http://127.0.0.1:4175", trace: "retain-on-failure",
    launchOptions: { executablePath: process.env.CAMPAIA_CHROMIUM_PATH } },
  webServer: [
    { command: "python3 -m tests_support.checkout_e2e_server", cwd: "../backend",
      url: "http://127.0.0.1:8100/auth/session", reuseExistingServer: false, timeout: 30_000,
      env: { CAMPAIA_E2E_ALLOWED_ORIGIN: "http://127.0.0.1:4175", CAMPAIA_E2E_PORT: "8100" } },
    { command: "npm run build && npm run start -- --hostname 127.0.0.1 --port 4175",
      url: "http://127.0.0.1:4175", reuseExistingServer: false, timeout: 180_000,
      env: { CAMPAIA_BFF_ORIGIN: "http://127.0.0.1:8100", NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE: "test" } },
  ],
  projects: [{ name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } }],
});
