/**
 * Network boundary for the browser-side Google -> Identity Platform token exchange.
 *
 * This file intentionally lives under src/lib/api/: the WP-01 security boundary allows
 * network I/O only in the central API layer (plus AuthProvider). The returned refresh
 * token, when Google includes one, is deliberately ignored and never persisted.
 */

export class IdentityPlatformExchangeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "IdentityPlatformExchangeError";
  }
}

interface IdentityPlatformResponse {
  idToken?: string;
  error?: {
    message?: string;
  };
}

export async function exchangeGoogleCredentialForIdentityPlatformToken(
  googleIdToken: string,
  options: { publicApi: string; requestUri?: string },
): Promise<string> {
  const credential = googleIdToken.trim();
  if (!credential) {
    throw new IdentityPlatformExchangeError(
      "O Google não retornou uma credencial de identidade válida.",
    );
  }

  const requestUri =
    options.requestUri?.trim() ??
    (typeof window !== "undefined" ? window.location.origin : "");
  if (!requestUri) {
    throw new IdentityPlatformExchangeError(
      "Não foi possível determinar a origem da aplicação para autenticação.",
    );
  }

  const response = await fetch(
    `https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key=${encodeURIComponent(
      options.publicApi,
    )}`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        postBody: new URLSearchParams({
          id_token: credential,
          providerId: "google.com",
        }).toString(),
        requestUri,
        returnIdpCredential: true,
        returnSecureToken: true,
      }),
    },
  );

  const body = (await response.json().catch(() => null)) as IdentityPlatformResponse | null;
  const idToken = body?.idToken?.trim();
  if (!response.ok || !idToken) {
    throw new IdentityPlatformExchangeError(
      "O Google Identity Platform não conseguiu concluir a autenticação.",
    );
  }

  return idToken;
}
