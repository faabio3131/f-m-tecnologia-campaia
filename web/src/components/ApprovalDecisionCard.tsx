"use client";

import { useState } from "react";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import type { ApprovalRequest } from "@/contracts/types";
import styles from "./ApprovalDecisionCard.module.css";

/**
 * WP-05: ninth deliberate client-side network call in web/src -- see
 * scripts/lib/security-boundaries.mjs's NETWORK_CALL_ALLOWED_FILES. Same CSRF discipline as
 * every other mutation in this app. POST .../decision requires both an Idempotency-Key and
 * X-Step-Up-Token (backend/api/deps.py require_idempotency_key, require_step_up) -- same
 * honest, non-empty marker pattern ConnectAccountCard.tsx established in WP-04, not a real
 * MFA challenge (none exists in this sandbox).
 *
 * Segregation of duties (roadmap WP-05 acceptance criterion: "tentativa de autoaprovação é
 * recusada visivelmente") is enforced ENTIRELY server-side
 * (campaia_core.permissions.can_approve) -- this component never hides or disables the
 * decision buttons based on "is this my own approval", since the UI has no reliable way to
 * know that ahead of the server's own check, and the point of the criterion is that the
 * REAL rejection is visible, not that the UI guesses it first.
 */
function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|; )campaia_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

const STEP_UP_MARKER = "web-ui-approval-decision-button-clicked";

export interface ApprovalDecisionCardProps {
  bffOrigin: string;
  approval: ApprovalRequest;
}

export function ApprovalDecisionCard({ bffOrigin, approval }: ApprovalDecisionCardProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function decide(decision: "APPROVE" | "REJECT" | "REQUEST_CHANGES") {
    setPending(true);
    setError(null);
    const csrfToken = readCsrfCookie();
    if (!csrfToken) {
      setError("Sessão sem cookie CSRF válido — recarregue a página.");
      setPending(false);
      return;
    }

    try {
      const response = await fetch(`${bffOrigin}/approvals/${approval.id}/decision`, {
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": csrfToken,
          "x-step-up-token": STEP_UP_MARKER,
          "idempotency-key": crypto.randomUUID(),
        },
        body: JSON.stringify({ decision }),
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { code?: string } | null;
        if (body?.code === "SEPARATION_OF_DUTIES") {
          setError("Você não pode decidir sobre a sua própria proposta.");
        } else {
          setError("Não foi possível registrar a decisão. Tente novamente.");
        }
        setPending(false);
        return;
      }
      window.location.reload();
    } catch {
      setError("Não foi possível registrar a decisão. Tente novamente.");
      setPending(false);
    }
  }

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <strong>{approval.reason}</strong>
        <Badge tone="neutral">{approval.status}</Badge>
      </div>
      <p className={styles.meta}>
        Solicitado por {approval.requested_by} · versão do plano {approval.plan_version}
        {approval.requires_dual_approval ? " · exige dupla aprovação" : ""}
      </p>
      {approval.status === "PENDING" ? (
        <div className={styles.actions}>
          <Button onClick={() => decide("APPROVE")} disabled={pending}>
            Aprovar
          </Button>
          <Button onClick={() => decide("REJECT")} disabled={pending} variant="secondary">
            Rejeitar
          </Button>
          <Button onClick={() => decide("REQUEST_CHANGES")} disabled={pending} variant="secondary">
            Pedir ajustes
          </Button>
        </div>
      ) : null}
      {error ? (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
