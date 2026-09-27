/**
 * Google Identity Platform client for the commercial Web flow.
 *
 * Production flow:
 * 1. Google Identity Services returns a Google OAuth ID token to the browser.
 * 2. The browser exchanges it through Identity Platform's official signInWithIdp
 *    endpoint for an Identity Platform/Firebase ID token.
 * 3. Only that short-lived ID token is passed to the CampaIA BFF, which creates the
 *    server-side CampaIA session. No refresh token is persisted in localStorage/sessionStorage.
 *
 * NEXT_PUBLIC_GOOGLE_IDENTITY_CLIENT_ID and NEXT_PUBLIC_FIREBASE_API_KEY are public
 * browser configuration, not tenant secrets. Real secrets/privileged credentials remain
 * server-side; deployment must restrict the Web API key and authorized origins in Google.
 */

export interface GoogleIdentityConfig {
  clientId: string;
  firebaseApiKey: string;
}

export type GoogleIdentityErrorCode =
  | "NOT_CONFIGURED"
  | "SCRIPT_LOAD_FAILED"
  | "MISSING_GOOGLE_CREDENTIAL"
  | "IDENTITY_PLATFORM_EXCHANGE_FAILED";

export class GoogleIdentityError extends Error {
  constructor(
    readonly code: GoogleIdentityErrorCode,
    message: string,
  ) {
    super(message);
    this.name = "GoogleIdentityError";
  }
}

export interface GoogleCredentialResponse {
  credential?: string;
  select_by?: string;
}

export interface GoogleAccountsIdApi {
  initialize(config: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
    auto_select?: boolean;
  }): void;
  renderButton(
    parent: HTMLElement,
    options: {
      type?: "standard" | "icon";
      theme?: "outline" | "filled_blue" | "filled_black";
      size?: "large" | "medium" | "small";
      text?: "signin_with" | "signup_with" | "continue_with" | "signin";
      shape?: "rectangular" | "pill" | "circle" | "square";
      logo_alignment?: "left" | "center";
      width?: number;
    },
  ): void;
  cancel?(): void;
}

declare global {
  interface Window {
    google?: {
      accounts?: {
        id?: GoogleAccountsIdApi;
      };
    };
  }
}

const GOOGLE_GSI_SCRIPT_SRC = "https://accounts.google.com/gsi/client";
let googleScriptPromise: Promise<GoogleAccountsIdApi> | null = null;

export function getGoogleIdentityConfig(): GoogleIdentityConfig | null {
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_IDENTITY_CLIENT_ID?.trim() ?? "";
  const firebaseApiKey = process.env.NEXT_PUBLIC_FIREBASE_API_KEY?.trim() ?? "";
  if (!clientId || !firebaseApiKey) return null;
  return { clientId, firebaseApiKey };
}

export function isGoogleIdentityConfigured(): boolean {
  return getGoogleIdentityConfig() !== null;
}

function currentGoogleApi(): GoogleAccountsIdApi | null {
  return window.google?.accounts?.id ?? null;
}

export function loadGoogleIdentityServices(): Promise<GoogleAccountsIdApi> {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return Promise.reject(
      new GoogleIdentityError(
        "SCRIPT_LOAD_FAILED",
        "Google Identity Services só pode ser carregado no navegador.",
      ),
    );
  }

  const ready = currentGoogleApi();
  if (ready) return Promise.resolve(ready);
  if (googleScriptPromise) return googleScriptPromise;

  googleScriptPromise = new Promise<GoogleAccountsIdApi>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      `script[src="${GOOGLE_GSI_SCRIPT_SRC}"]`,
    );
    const script = existing ?? document.createElement("script");

    const onLoad = () => {
      const api = currentGoogleApi();
      if (api) {
        resolve(api);
        return;
      }
      reject(
        new GoogleIdentityError(
          "SCRIPT_LOAD_FAILED",
          "Google Identity Services carregou sem disponibilizar a API esperada.",
        ),
      );
    };
    const onError = () => {
      reject(
        new GoogleIdentityError(
          "SCRIPT_LOAD_FAILED",
          "Não foi possível carregar o Google Identity Services.",
        ),
      );
    };

    script.addEventListener("load", onLoad, { once: true });
    script.addEventListener("error", onError, { once: true });

    if (!existing) {
      script.src = GOOGLE_GSI_SCRIPT_SRC;
      script.async = true;
      script.defer = true;
      script.referrerPolicy = "strict-origin-when-cross-origin";
      script.dataset.campaiaGoogleIdentity = "true";
      document.head.appendChild(script);
    }
  }).catch((error) => {
    googleScriptPromise = null;
    throw error;
  });

  return googleScriptPromise;
}

interface IdentityPlatformResponse {
  idToken?: string;
  error?: {
    message?: string;
  };
}

export async function exchangeGoogleCredentialForIdentityPlatformToken(
  googleIdToken: string,
  options: { firebaseApiKey: string; requestUri?: string },
): Promise<string> {
  const credential = googleIdToken.trim();
  if (!credential) {
    throw new GoogleIdentityError(
      "MISSING_GOOGLE_CREDENTIAL",
      "O Google não retornou uma credencial de identidade válida.",
    );
  }

  const requestUri =
    options.requestUri?.trim() ??
    (typeof window !== "undefined" ? window.location.origin : "");
  if (!requestUri) {
    throw new GoogleIdentityError(
      "IDENTITY_PLATFORM_EXCHANGE_FAILED",
      "Não foi possível determinar a origem da aplicação para autenticação.",
    );
  }

  const response = await fetch(
    `https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key=${encodeURIComponent(
      options.firebaseApiKey,
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
    throw new GoogleIdentityError(
      "IDENTITY_PLATFORM_EXCHANGE_FAILED",
      "O Google Identity Platform não conseguiu concluir a autenticação.",
    );
  }

  return idToken;
}
