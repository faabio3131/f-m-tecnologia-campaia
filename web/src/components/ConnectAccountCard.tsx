"use client";

import { useState } from "react";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import type { Capability, Connection } from "@/contracts/types";
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
 *
 * WP-09 completes the connection lifecycle: "Desconectar" (DELETE /connections/{id}, CSRF +
 * step-up + idempotency-key, same discipline as connecting) and the real capabilities list
 * (`capabilities` prop, fetched server-side in onboarding/page.tsx via
 * getServerConnectionCapabilities -- this component never fetches them itself, matching this
 * app's boundary that every GET runs server-side).
 */
function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|; )campaia_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

const CONNECT_STEP_UP_MARKER = "web-ui-connect-account-button-clicked";
const DISCONNECT_STEP_UP_MARKER = "web-ui-disconnect-account-button-clicked";

export interface ConnectAccountCardProps {
  bffOrigin: string;
  provider: "GOOGLE_ADS" | "META" | "WHATSAPP";
  label: string;
  connection: Connection | undefined;
  /** WP-09: undefined when not connected; null when the capabilities read itself failed;
   * an array (always length 2 today, GOOGLE_ADS/META_ADS PUBLISH) when it succeeded. */
  capabilities?: Capability[] | null;
}

export function ConnectAccountCard({
  bffOrigin,
  provider,
  label,
  connection,
  capabilities,
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
          "x-step-up-token": CONNECT_STEP_UP_MARKER,
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
          "x-step-up-token": CONNECT_STEP_UP_MARKER,
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

  async function handleDisconnect() {
    if (!connection) {
      return;
    }
    setPending(true);
    setError(null);
    const csrfToken = readCsrfCookie();
    if (!csrfToken) {
      setError("Sessão sem cookie CSRF válido — recarregue a página.");
      setPending(false);
      return;
    }

    try {
      const response = await fetch(`${bffOrigin}/connections/${connection.id}`, {
        method: "DELETE",
        credentials: "include",
        headers: {
          "x-csrf-token": csrfToken,
          "x-step-up-token": DISCONNECT_STEP_UP_MARKER,
          "idempotency-key": crypto.randomUUID(),
        },
      });
      if (!response.ok) {
        setError("Não foi possível desconectar. Tente novamente.");
        setPending(false);
        return;
      }
      window.location.reload();
    } catch {
      setError("Não foi possível desconectar. Tente novamente.");
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
        <>
          <p className={styles.accountName}>{connection.display_name}</p>
          {capabilities === null ? (
            <p className={styles.error} role="alert">
              Não foi possível carregar as capacidades desta conexão.
            </p>
          ) : capabilities && capabilities.length > 0 ? (
            <ul className={styles.capabilities}>
              {capabilities.map((cap) => (
                <li key={cap.capability_key}>
                  {cap.capability_key}: {cap.supported ? "suportada" : "não suportada"}
                  {cap.requires_approval ? " (exige aprovação)" : ""}
                </li>
              ))}
            </ul>
          ) : null}
          <Button onClick={handleDisconnect} disabled={pending} variant="secondary">
            {pending ? "Desconectando…" : "Desconectar"}
          </Button>
        </>
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
