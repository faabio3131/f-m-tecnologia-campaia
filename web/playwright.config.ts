import { defineConfig, devices } from "@playwright/test";

const PORT = 4173;

export default defineConfig({
  testDir: "./e2e",
  // So do smoke do WP-01 (`foundation.spec.ts`) -- este config nao sobe o backend
  // real nem NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE=test, entao nao tem como rodar
  // `session-protocol.spec.ts` (Etapa 2), que exige `playwright.session.config.ts`.
  testMatch: /foundation\.spec\.ts/,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
    launchOptions: {
      executablePath: process.env.CAMPAIA_CHROMIUM_PATH,
    },
  },
  webServer: {
    command: `npm run start -- --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
  projects: [
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile-chromium",
      use: { ...devices["Pixel 7"] },
    },
  ],
});
