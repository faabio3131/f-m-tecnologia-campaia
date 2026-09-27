"use client";

import { useEffect, useRef, useState } from "react";
import {
  GoogleIdentityError,
  exchangeGoogleCredentialForIdentityPlatformToken,
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
  if (error instanceof GoogleIdentityError) return error.message;
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
    if (!config) return;
    const container = containerRef.current;
    if (!container) return;

    let active = true;
    setSetupError(null);

    loadGoogleIdentityServices()
      .then((api) => {
        if (!active) return;

        api.initialize({
          client_id: config.clientId,
          auto_select: false,
          callback: (response) => {
            if (!active || disabledRef.current) return;
            void (async () => {
              try {
                const googleCredential = response.credential?.trim() ?? "";
                const idToken =
                  await exchangeGoogleCredentialForIdentityPlatformToken(
                    googleCredential,
                    { firebaseApiKey: config.firebaseApiKey },
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
  }, [config?.clientId, config?.firebaseApiKey, text]);

  if (!config) return null;

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
