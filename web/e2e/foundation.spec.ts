import { expect, test } from "@playwright/test";

test.describe("CampaIA Web entrypoint smoke", () => {
  test("redirects the product root to the real login entrypoint", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login$/);
    await expect(
      page.getByRole("heading", { level: 1, name: "Entrar no CampaIA" }),
    ).toBeVisible();
  });

  test("renders without horizontal overflow at the login entrypoint", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login$/);
    const hasHorizontalScroll = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(hasHorizontalScroll).toBe(false);
  });
});
