import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  IdentityPlatformExchangeError,
  exchangeGoogleCredentialForIdentityPlatformToken,
} from "@/lib/api/identity-platform";
import {
  getGoogleIdentityConfig,
  isGoogleIdentityConfigured,
} from "@/lib/auth/google-identity-client";

describe("Google Identity Platform Web client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("fails closed when either public browser setting is missing", () => {
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_IDENTITY_CLIENT_ID", "");
    vi.stubEnv("NEXT_PUBLIC_IDENTITY_PLATFORM_PUBLIC_API", "");
    expect(getGoogleIdentityConfig()).toBeNull();
    expect(isGoogleIdentityConfigured()).toBe(false);

    vi.stubEnv("NEXT_PUBLIC_GOOGLE_IDENTITY_CLIENT_ID", "client.apps.googleusercontent.com");
    expect(getGoogleIdentityConfig()).toBeNull();
  });

  it("exposes only the public client configuration when both values exist", () => {
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_IDENTITY_CLIENT_ID", " client.apps.googleusercontent.com ");
    vi.stubEnv("NEXT_PUBLIC_IDENTITY_PLATFORM_PUBLIC_API", " public-web-api ");

    expect(getGoogleIdentityConfig()).toEqual({
      clientId: "client.apps.googleusercontent.com",
      identityPlatformPublicApi: "public-web-api",
    });
    expect(isGoogleIdentityConfigured()).toBe(true);
  });

  it("exchanges a Google ID token for an Identity Platform ID token", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ idToken: "firebase-id-token", refreshToken: "discarded" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const result = await exchangeGoogleCredentialForIdentityPlatformToken(
      "google-id-token",
      {
        publicApi: "public-web-api",
        requestUri: "https://app.campaia.test",
      },
    );

    expect(result).toBe("firebase-id-token");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe(
      "https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key=public-web-api",
    );
    expect(init?.method).toBe("POST");
    const body = JSON.parse(String(init?.body));
    expect(body.requestUri).toBe("https://app.campaia.test");
    expect(body.returnSecureToken).toBe(true);
    expect(body.returnIdpCredential).toBe(true);
    expect(body.postBody).toContain("id_token=google-id-token");
    expect(body.postBody).toContain("providerId=google.com");
  });

  it("never accepts a successful HTTP response without an Identity Platform ID token", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ refreshToken: "must-not-be-used" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    await expect(
      exchangeGoogleCredentialForIdentityPlatformToken("google-id-token", {
        publicApi: "public-web-api",
        requestUri: "https://app.campaia.test",
      }),
    ).rejects.toBeInstanceOf(IdentityPlatformExchangeError);
  });

  it("maps an Identity Platform rejection to a fail-closed authentication error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { message: "INVALID_IDP_RESPONSE" } }), {
        status: 400,
        headers: { "content-type": "application/json" },
      }),
    );

    await expect(
      exchangeGoogleCredentialForIdentityPlatformToken("google-id-token", {
        publicApi: "public-web-api",
        requestUri: "https://app.campaia.test",
      }),
    ).rejects.toBeInstanceOf(IdentityPlatformExchangeError);
  });
});
