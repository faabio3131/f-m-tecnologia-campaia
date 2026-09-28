import { test, expect } from "@playwright/test";

const FRESH_OWNER = "test-identity-e2e-test-id-token-fresh-commercial-owner";
const FRESH_MEMBER = "accept-invite-identity-e2e-test-id-token-fresh-commercial-member";

test.describe("F1 onboarding comercial sem tenant pre-seedado", () => {
  // The backend state is intentionally persistent for the life of the E2E server. A retry
  // after a partial success would no longer represent a brand-new identity, so this
  // certification scenario is single-attempt by design.
  test.describe.configure({ retries: 0 });

  test("novo cliente cria tenant, unidade Principal, convida usuario e preserva lifecycle", async ({
    page,
    browser,
  }) => {
    await page.context().clearCookies();
    await page.goto("/login");

    // This identity exists ONLY in the deterministic IdP verifier, not in any tenant seed.
    // Normal login must fail closed and expose the explicit product onboarding flow.
    const loginResponse = page.waitForResponse(
      (r) => r.url().endsWith("/auth/session") && r.request().method() === "POST",
    );
    await page.getByTestId(FRESH_OWNER).click();
    expect((await loginResponse).status()).toBe(403);
    await expect(page.getByTestId("commercial-onboarding-form")).toBeVisible();

    await page.getByLabel("Nome da empresa").fill("Empresa Comercial E2E");
    await page.getByLabel("CNPJ/Documento (quando aplicável)").fill("44.444.444/0001-44");
    await page.getByLabel("Segmento / tipo de negócio").fill("serviços");
    await page.getByLabel("Idioma").fill("pt-BR");
    await page.getByLabel("Fuso horário").fill("America/Sao_Paulo");
    await expect(page.getByText(/Entrada comercial:.*Teste grátis/)).toBeVisible();

    const onboardingResponsePromise = page.waitForResponse(
      (r) => r.url().endsWith("/onboarding/tenant") && r.request().method() === "POST",
    );
    await page.getByTestId("create-commercial-tenant").click();
    const onboardingResponse = await onboardingResponsePromise;
    expect(onboardingResponse.status()).toBe(201);
    const onboarding = await onboardingResponse.json();
    expect(onboarding.organization.document).toBe("44444444000144");
    expect(onboarding.membership.roles).toEqual(["OWNER"]);
    expect(onboarding.session.business_unit_id).toBe(
      onboarding.organization.default_business_unit_id,
    );

    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByText(onboarding.organization.tenant_id).first()).toBeVisible();

    // F2 organization administration: create a second unit entirely through the product.
    await page.goto("/settings/organization");
    await expect(page.getByRole("heading", { name: "Organização" })).toBeVisible();
    await page.getByLabel("Nome da unidade").fill("Comercial E2E");
    const unitResponsePromise = page.waitForResponse(
      (r) => r.url().endsWith("/business-units") && r.request().method() === "POST",
    );
    await page.getByTestId("create-business-unit").click();
    const unitResponse = await unitResponsePromise;
    expect(unitResponse.status()).toBe(201);
    const commercialUnit = await unitResponse.json();

    // Owner/Admin surface: create a real invitation. The raw token is returned only once;
    // no membership is inserted manually by the test.
    await page.goto("/settings/users");
    await expect(page.getByRole("heading", { name: "Usuários" })).toBeVisible();
    await page.getByLabel("E-mail").fill("fresh-member@commercial-e2e.campaia.test");
    await page.getByLabel("Unidade de negócio").first().selectOption(commercialUnit.id);

    const invitationResponsePromise = page.waitForResponse(
      (r) => r.url().endsWith("/member-invitations") && r.request().method() === "POST",
    );
    await page.getByTestId("create-member-invitation").click();
    const invitationResponse = await invitationResponsePromise;
    expect(invitationResponse.status()).toBe(201);
    const invitation = await invitationResponse.json();
    expect(invitation.accept_token).toBeTruthy();

    // Separate browser = separate cookies/session, exactly as two real users.
    const memberContext = await browser.newContext();
    const memberPage = await memberContext.newPage();
    await memberPage.goto(
      "/accept-invite?token=" + encodeURIComponent(invitation.accept_token),
    );
    const acceptResponsePromise = memberPage.waitForResponse(
      (r) =>
        r.url().endsWith("/onboarding/invitations/accept") &&
        r.request().method() === "POST",
    );
    await memberPage.getByTestId(FRESH_MEMBER).click();
    const acceptResponse = await acceptResponsePromise;
    expect(acceptResponse.status()).toBe(200);
    const accepted = await acceptResponse.json();
    expect(accepted.organization.tenant_id).toBe(onboarding.organization.tenant_id);
    expect(accepted.membership.status).toBe("ACTIVE");
    expect(accepted.membership.roles).toEqual(["VIEWER"]);
    expect(accepted.membership.business_unit_id).toBe(commercialUnit.id);
    await expect(memberPage).toHaveURL(/\/dashboard/);

    // The owner now sees the accepted membership through the tenant-scoped API.
    await page.reload();
    await expect(
      page.getByText("fresh-member@commercial-e2e.campaia.test"),
    ).toBeVisible();

    const memberId = accepted.membership.id;

    // F2 role administration is a real mutation. It revokes the member's stale session,
    // because roles/unit are captured into the server-side session at login.
    await page.getByTestId("role-" + memberId + "-MARKETER").check();
    await page.getByTestId("role-" + memberId + "-VIEWER").uncheck();
    const accessResponsePromise = page.waitForResponse(
      (r) =>
        r.url().endsWith("/memberships/" + memberId) &&
        r.request().method() === "PATCH",
    );
    await page.getByTestId("save-access-" + memberId).click();
    const accessResponse = await accessResponsePromise;
    expect(accessResponse.status()).toBe(200);
    expect((await accessResponse.json()).roles).toEqual(["MARKETER"]);

    await memberPage.reload();
    await expect(memberPage).toHaveURL(/\/login/);
    const roleReloginResponse = memberPage.waitForResponse(
      (r) => r.url().endsWith("/auth/session") && r.request().method() === "POST",
    );
    await memberPage.getByTestId(FRESH_MEMBER).click();
    const roleRelogin = await roleReloginResponse;
    expect(roleRelogin.status()).toBe(200);
    expect((await roleRelogin.json()).roles).toEqual(["MARKETER"]);
    await expect(memberPage).toHaveURL(/\/dashboard/);

    const deactivateResponsePromise = page.waitForResponse(
      (r) =>
        r.url().endsWith("/memberships/" + memberId + "/deactivate") &&
        r.request().method() === "POST",
    );
    await page.getByTestId("deactivate-" + memberId).click();
    expect((await deactivateResponsePromise).status()).toBe(200);

    // Deactivation revokes any session that captured this membership.
    await memberPage.reload();
    await expect(memberPage).toHaveURL(/\/login/);

    const reactivateResponsePromise = page.waitForResponse(
      (r) =>
        r.url().endsWith("/memberships/" + memberId + "/reactivate") &&
        r.request().method() === "POST",
    );
    await page.getByTestId("reactivate-" + memberId).click();
    expect((await reactivateResponsePromise).status()).toBe(200);

    // Same membership id/history comes back; normal login works again after reactivation.
    const memberLoginResponse = memberPage.waitForResponse(
      (r) => r.url().endsWith("/auth/session") && r.request().method() === "POST",
    );
    await memberPage
      .getByTestId("test-identity-e2e-test-id-token-fresh-commercial-member")
      .click();
    expect((await memberLoginResponse).status()).toBe(200);
    await expect(memberPage).toHaveURL(/\/dashboard/);
    await expect(memberPage.getByText(onboarding.organization.tenant_id).first()).toBeVisible();

    await memberContext.close();
  });
});
