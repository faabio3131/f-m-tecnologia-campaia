"use client";

import { useState } from "react";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import type { Connection } from "@/contracts/types";
import styles from "./ConnectAccountCard.module.css";

/**
 * WP-04: fifth deliberate client-side network call in web/src -- see
 * scripts/lib/security-boundaries.mjs's NETWORK_CALL_ALLOWED_FILES. Same CSRF discipline as
 * every other mutation in this app.
 *
 * No real provider exists yet (roadmap WP-04: "ainda sem provider real por tras", "usar o
 * simulador ja citado no dominio") -- there is no real account list to show the user, so
 * this never pretends one exists. Clicking "Conectar" drives the two real backend calls a
 * genuine flow would need (start, then complete with the account the provider would have
 * returned) back to back, immediately, and is labeled "(simulado)" throughout so nothing
 * here is mistaken for a real OAuth connection.
 *
 * Both /connections/oauth/start and /connections/oauth/complete require X-Step-Up-Token
 * (backend/api/deps.py require_step_up) -- in this sandbox that header's value is only
 * ever checked for non-emptiness, never a real re-authentication challenge (see
 * deps.py's own docstring). This is the first place the Web frontend sends that header;
 * it sends a literal marker naming what actually happened (an explicit click on this
 * button, nothing more) rather than pretending a real MFA step occurred.
 */
function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|; )campaia_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

const STEP_UP_MARKER = "web-ui-connect-account-button-clicked";

export interface ConnectAccountCardProps {
  bffOrigin: string;
  provider: "GOOGLE_ADS" | "META" | "WHATSAPP";
  label: string;
  connection: Connection | undefined;
}

export function ConnectAccountCard({
  bffOrigin,
  provider,
  label,
  connection,
}: ConnectAccountCardProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConnect() {
    setPending(true);
    setError(null);
    const csrfToken = readCsrfCookie();
    if (!csrfToken) {
      setError("Sessão sem cookie CSRF válido — recarregue a página.");
      setPending(false);
      return;
    }

    try {
      const startResponse = await fetch(`${bffOrigin}/connections/oauth/start`, {
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": csrfToken,
          "x-step-up-token": STEP_UP_MARKER,
        },
        body: JSON.stringify({ provider }),
      });
      if (!startResponse.ok) {
        setError("Não foi possível iniciar a conexão. Tente novamente.");
        setPending(false);
        return;
      }
      const { state } = (await startResponse.json()) as { state: string };

      const completeResponse = await fetch(`${bffOrigin}/connections/oauth/complete`, {
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": csrfToken,
          "x-step-up-token": STEP_UP_MARKER,
          "idempotency-key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          state,
          external_account_id: `sim-${provider.toLowerCase()}-${state.slice(0, 8)}`,
          display_name: `${label} (simulado)`,
        }),
      });
      if (!completeResponse.ok) {
        setError("Não foi possível concluir a conexão. Tente novamente.");
        setPending(false);
        return;
      }
      window.location.reload();
    } catch {
      setError("Não foi possível conectar. Tente novamente.");
      setPending(false);
    }
  }

  const isConnected = connection !== undefined && connection.status === "ACTIVE";

  return (
    <div className={styles.card} data-testid={`connect-card-${provider}`}>
      <div className={styles.header}>
        <span className={styles.label}>{label}</span>
        {isConnected ? (
          <Badge tone="accent">Conectado (simulado)</Badge>
        ) : (
          <Badge tone="neutral">Não conectado</Badge>
        )}
      </div>
      {isConnected ? (
        <p className={styles.accountName}>{connection.display_name}</p>
      ) : (
        <Button onClick={handleConnect} disabled={pending} variant="secondary">
          {pending ? "Conectando…" : "Conectar (simulado)"}
        </Button>
      )}
      {error ? (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
