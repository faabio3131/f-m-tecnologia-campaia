import { expect, test } from "@playwright/test";

const BFF_HOST_PATTERNS = [/\/me\b/, /localhost:8000/, /:8000\//];

test.describe("CampaIA Web Foundation (WP-01) smoke", () => {
  test("loads the foundation page with no critical console errors and no BFF network calls", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    const bffRequests: string[] = [];

    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(message.text());
      }
    });

    page.on("request", (request) => {
      const url = request.url();
      if (BFF_HOST_PATTERNS.some((pattern) => pattern.test(url))) {
        bffRequests.push(url);
      }
    });

    await page.goto("/");

    await expect(
      page.getByRole("heading", { level: 1, name: "CampaIA" }),
    ).toBeVisible();

    await expect(
      page.getByText("CampaIA Web Foundation — WP-01"),
    ).toBeVisible();

    await expect(
      page.getByText(
        "Nenhuma sessão, tenant ou integração real está ativa nesta tela.",
      ),
    ).toBeVisible();

    await expect(
      page.getByText(/Fixture local \(schema Me, contrato bff-openapi\.yaml\)/),
    ).toBeVisible();

    expect(consoleErrors, `console errors: ${consoleErrors.join("; ")}`).toEqual(
      [],
    );
    expect(
      bffRequests,
      `unexpected BFF-like requests: ${bffRequests.join(", ")}`,
    ).toEqual([]);
  });

  test("renders without horizontal overflow at the current viewport", async ({
    page,
  }) => {
    await page.goto("/");
    const hasHorizontalScroll = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(hasHorizontalScroll).toBe(false);
  });
});
