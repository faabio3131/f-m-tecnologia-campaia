"use client";

import { useState } from "react";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import type { PolicyDecision } from "@/contracts/types";
import styles from "./ValidationPanel.module.css";

/**
 * WP-05: eighth deliberate client-side network call in web/src -- see
 * scripts/lib/security-boundaries.mjs's NETWORK_CALL_ALLOWED_FILES. Same CSRF discipline as
 * every other mutation in this app.
 *
 * Two distinct calls, both real: POST .../validate (no side effect on external systems,
 * emits a PolicyDecision -- neither the contract nor routes_campaigns.py's validate_campaign
 * requires an Idempotency-Key here, since re-validating is not a "create" and always
 * reflects the campaign's CURRENT plan) and POST /approvals (puts a PENDING ApprovalRequest
 * on record when the decision says a human must approve -- also no Idempotency-Key on this
 * route, see routes_approvals.py create_approval). Segregation of duties itself is enforced
 * entirely server-side (campaia_core.permissions.can_approve) on the decision screen
 * (ApprovalDecisionCard.tsx), never re-implemented here.
 */
function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|; )campaia_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

const OUTCOME_TONE: Record<string, "accent" | "warning" | "neutral"> = {
  APPROVABLE: "accent",
  BLOCKED: "warning",
  NEEDS_CHANGES: "warning",
};

export interface ValidationPanelProps {
  bffOrigin: string;
  campaignId: string;
  hasPendingApproval: boolean;
}

export function ValidationPanel({
  bffOrigin,
  campaignId,
  hasPendingApproval,
}: ValidationPanelProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decision, setDecision] = useState<PolicyDecision | null>(null);

  async function handleValidate() {
    setPending(true);
    setError(null);
    const csrfToken = readCsrfCookie();
    if (!csrfToken) {
      setError("Sessão sem cookie CSRF válido — recarregue a página.");
      setPending(false);
      return;
    }

    try {
      const response = await fetch(
        `${bffOrigin}/campaigns/${encodeURIComponent(campaignId)}/validate`,
        {
          method: "POST",
          credentials: "include",
          headers: { "x-csrf-token": csrfToken },
        },
      );
      if (!response.ok) {
        setError("Não foi possível validar a campanha. Tente novamente.");
        setPending(false);
        return;
      }
      setDecision((await response.json()) as PolicyDecision);
      setPending(false);
    } catch {
      setError("Não foi possível validar a campanha. Tente novamente.");
      setPending(false);
    }
  }

  async function handleRequestApproval() {
    setPending(true);
    setError(null);
    const csrfToken = readCsrfCookie();
    if (!csrfToken) {
      setError("Sessão sem cookie CSRF válido — recarregue a página.");
      setPending(false);
      return;
    }

    try {
      const response = await fetch(`${bffOrigin}/approvals`, {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json", "x-csrf-token": csrfToken },
        body: JSON.stringify({
          campaign_id: campaignId,
          kind: "PUBLISH",
          requires_dual_approval: decision?.requires_dual_approval ?? false,
        }),
      });
      if (!response.ok) {
        setError("Não foi possível solicitar aprovação. Tente novamente.");
        setPending(false);
        return;
      }
      window.location.reload();
    } catch {
      setError("Não foi possível solicitar aprovação. Tente novamente.");
      setPending(false);
    }
  }

  return (
    <div className={styles.wrapper}>
      <Button onClick={handleValidate} disabled={pending}>
        {pending ? "Validando…" : "Validar"}
      </Button>

      {decision ? (
        <div className={styles.result}>
          <Badge tone={OUTCOME_TONE[decision.outcome ?? ""] ?? "neutral"}>
            {decision.outcome}
          </Badge>
          {decision.findings && decision.findings.length > 0 ? (
            <ul className={styles.findings}>
              {decision.findings.map((finding, index) => (
                <li key={index} className={styles.finding}>
                  <Badge tone={finding.severity === "BLOCKING" ? "warning" : "neutral"}>
                    {finding.severity}
                  </Badge>{" "}
                  {finding.explanation}
                </li>
              ))}
            </ul>
          ) : null}

          {decision.requires_human_approval ? (
            hasPendingApproval ? (
              <p className={styles.note}>Aprovação já solicitada — aguardando decisão.</p>
            ) : (
              <Button onClick={handleRequestApproval} disabled={pending} variant="secondary">
                {pending ? "Solicitando…" : "Solicitar aprovação"}
              </Button>
            )
          ) : (
            <p className={styles.note}>Esta campanha não exige aprovação humana.</p>
          )}
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
