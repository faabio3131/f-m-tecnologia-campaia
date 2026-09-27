"use client";

import { useEffect, useRef, useState } from "react";
import {
  IdentityPlatformExchangeError,
  exchangeGoogleCredentialForIdentityPlatformToken,
} from "../lib/api/identity-platform";
import {
  GoogleIdentityError,
  getGoogleIdentityConfig,
  loadGoogleIdentityServices,
} from "../lib/auth/google-identity-client";

interface GoogleIdentityButtonProps {
  onIdToken: (idToken: string) => Promise<void> | void;
  onError?: (message: string) => void;
  disabled?: boolean;
  text?: "signin_with" | "signup_with" | "continue_with";
}

function friendlyGoogleError(error: unknown): string {
  if (
    error instanceof GoogleIdentityError ||
    error instanceof IdentityPlatformExchangeError
  ) {
    return error.message;
  }
  return "Não foi possível concluir a autenticação com o Google.";
}

export function GoogleIdentityButton({
  onIdToken,
  onError,
  disabled = false,
  text = "continue_with",
}: GoogleIdentityButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const onIdTokenRef = useRef(onIdToken);
  const onErrorRef = useRef(onError);
  const disabledRef = useRef(disabled);
  const [setupError, setSetupError] = useState<string | null>(null);
  const config = getGoogleIdentityConfig();
  const clientId = config?.clientId ?? null;
  const identityPlatformPublicApi = config?.identityPlatformPublicApi ?? null;

  useEffect(() => {
    onIdTokenRef.current = onIdToken;
  }, [onIdToken]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    disabledRef.current = disabled;
  }, [disabled]);

  useEffect(() => {
    if (!clientId || !identityPlatformPublicApi) return;
    const container = containerRef.current;
    if (!container) return;

    let active = true;
    setSetupError(null);

    loadGoogleIdentityServices()
      .then((api) => {
        if (!active) return;

        api.initialize({
          client_id: clientId,
          auto_select: false,
          callback: (response) => {
            if (!active || disabledRef.current) return;
            void (async () => {
              try {
                const googleCredential = response.credential?.trim() ?? "";
                if (!googleCredential) {
                  throw new GoogleIdentityError(
                    "MISSING_GOOGLE_CREDENTIAL",
                    "O Google não retornou uma credencial de identidade válida.",
                  );
                }
                const idToken =
                  await exchangeGoogleCredentialForIdentityPlatformToken(
                    googleCredential,
                    { publicApi: identityPlatformPublicApi },
                  );
                if (active) await onIdTokenRef.current(idToken);
              } catch (error) {
                if (!active) return;
                const message = friendlyGoogleError(error);
                setSetupError(message);
                onErrorRef.current?.(message);
              }
            })();
          },
        });

        container.replaceChildren();
        api.renderButton(container, {
          type: "standard",
          theme: "outline",
          size: "large",
          text,
          shape: "rectangular",
          logo_alignment: "left",
          width: 320,
        });
      })
      .catch((error) => {
        if (!active) return;
        const message = friendlyGoogleError(error);
        setSetupError(message);
        onErrorRef.current?.(message);
      });

    return () => {
      active = false;
      container.replaceChildren();
    };
  }, [clientId, identityPlatformPublicApi, text]);

  if (!clientId || !identityPlatformPublicApi) return null;

  return (
    <div>
      <div
        ref={containerRef}
        data-testid="google-identity-button"
        aria-disabled={disabled}
        style={{
          opacity: disabled ? 0.65 : 1,
          pointerEvents: disabled ? "none" : "auto",
          minHeight: 44,
        }}
      />
      {setupError ? (
        <p role="alert" style={{ margin: "0.5rem 0 0" }}>
          {setupError}
        </p>
      ) : null}
    </div>
  );
}
