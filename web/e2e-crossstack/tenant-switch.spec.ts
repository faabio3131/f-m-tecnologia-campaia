import { expect, test } from "@playwright/test";

/**
 * WP-03 cross-stack E2E: real login (OIDC Authorization Code + PKCE against the real test
 * identity provider, backend/api/test_idp.py) through an actual browser, then a real tenant
 * switch through the UI (TenantSwitcher -> POST /session/switch-tenant), reinforcing the
 * WP-02 cross-tenant isolation guarantee at the UI level (roadmap: "nenhum dado de outro
 * tenant deve aparecer nem transitoriamente").
 *
 * Uses `multi_tenant_owner` (api/test_idp.py) -- OWNER in demo-tenant (active on login),
 * VIEWER in other-tenant -- the only fixture identity with more than one real membership.
 */
async function loginAsMultiTenantOwner(page: import("@playwright/test").Page) {
  await page.goto("/dashboard");
  await page.getByRole("link", { name: "Entrar" }).click();
  await page
    .getByRole("button", { name: /owner@multi-tenant\.test/ })
    .click();
  await expect(page).toHaveURL(/\/dashboard$/);
  // `next dev` (this harness's only option -- see playwright.crossstack.config.ts) needs a
  // moment past navigation to finish hydrating TenantSwitcher/LogoutButton -- Playwright's
  // own actionability checks (visible/enabled/stable) don't know about React hydration, so
  // an interaction dispatched too early reaches a <select> whose onChange isn't wired up
  // yet (confirmed by reproducing it: selectOption "succeeds" at the DOM level with zero
  // network request following it). Waiting for network idle is a reliable proxy here.
  await page.waitForLoadState("networkidle");
}

test.describe("CampaIA Web /dashboard tenant switch (WP-03) cross-stack E2E", () => {
  test("login shows demo-tenant active with both memberships listed", async ({ page }) => {
    await loginAsMultiTenantOwner(page);

    await expect(page.getByText("user-owner-3")).toBeVisible();
    const select = page.getByLabel("Tenant ativo");
    await expect(select).toBeVisible();
    await expect(select).toHaveValue("demo-tenant");

    const options = select.locator("option");
    await expect(options).toHaveCount(2);
    await expect(options.nth(0)).toContainText("demo-tenant");
    await expect(options.nth(1)).toContainText("other-tenant");
  });

  test("switching tenant updates the active tenant and its roles, never mixing the two", async ({
    page,
  }) => {
    await loginAsMultiTenantOwner(page);

    // Baseline: the ACTIVE session panel (never the tenant picker, which legitimately
    // lists every membership's roles so the user knows what they're switching to) reflects
    // demo-tenant/OWNER only -- other-tenant's VIEWER role must never appear there, not
    // even transiently.
    const statusPanel = page.locator("dl", { hasText: "tenant_id" });
    await expect(statusPanel).toContainText("demo-tenant");
    await expect(statusPanel).toContainText("OWNER");
    await expect(statusPanel).not.toContainText("other-tenant");
    await expect(statusPanel).not.toContainText("VIEWER");

    await page.getByLabel("Tenant ativo").selectOption("other-tenant");
    await expect(page).toHaveURL(/\/dashboard$/);

    const selectAfter = page.getByLabel("Tenant ativo");
    await expect(selectAfter).toHaveValue("other-tenant");

    // Post-switch: other-tenant/VIEWER only -- demo-tenant's OWNER role for THIS user must
    // no longer be reflected as the active role anywhere in the session panel.
    const statusPanelAfter = page.locator("dl", { hasText: "tenant_id" });
    await expect(statusPanelAfter).toContainText("other-tenant");
    await expect(statusPanelAfter).toContainText("VIEWER");
    await expect(statusPanelAfter).not.toContainText("demo-tenant");
    await expect(statusPanelAfter).not.toContainText("OWNER");
  });

  test("switching tenant invalidates the previous session cookie server-side", async ({
    page,
    context,
  }) => {
    await loginAsMultiTenantOwner(page);
    const cookiesBefore = await context.cookies();
    const sessionBefore = cookiesBefore.find((c) => c.name === "campaia_session");
    expect(sessionBefore).toBeTruthy();

    await page.getByLabel("Tenant ativo").selectOption("other-tenant");
    await expect(page).toHaveURL(/\/dashboard$/);

    const cookiesAfter = await context.cookies();
    const sessionAfter = cookiesAfter.find((c) => c.name === "campaia_session");
    expect(sessionAfter).toBeTruthy();
    expect(sessionAfter?.value).not.toEqual(sessionBefore?.value);
  });
});
