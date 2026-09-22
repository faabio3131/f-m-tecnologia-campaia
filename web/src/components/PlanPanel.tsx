"use client";

import { useState } from "react";
import { Button } from "@/components/Button";
import type { CampaignPlan } from "@/contracts/types";
import styles from "./PlanPanel.module.css";

/**
 * WP-05: seventh deliberate client-side network call in web/src -- see
 * scripts/lib/security-boundaries.mjs's NETWORK_CALL_ALLOWED_FILES. Same CSRF discipline as
 * every other mutation in this app. POST .../plan/regenerate requires an Idempotency-Key
 * (backend/api/deps.py require_idempotency_key), generated fresh per submit -- a real new
 * strategy request each click, never a replay of the previous one.
 *
 * "adjustments" is optional free text (contract: maxLength 2000) the user can give the
 * strategist agent -- there is no other input to the plan besides the brief itself.
 */
function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|; )campaia_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export interface PlanPanelProps {
  bffOrigin: string;
  campaignId: string;
  plan: CampaignPlan;
}

export function PlanPanel({ bffOrigin, campaignId, plan }: PlanPanelProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [adjustments, setAdjustments] = useState("");

  async function handleGenerate() {
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
        `${bffOrigin}/campaigns/${encodeURIComponent(campaignId)}/plan/regenerate`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "content-type": "application/json",
            "x-csrf-token": csrfToken,
            "idempotency-key": crypto.randomUUID(),
          },
          body: JSON.stringify(adjustments.trim() ? { adjustments: adjustments.trim() } : {}),
        },
      );
      if (!response.ok) {
        setError("Não foi possível gerar a estratégia. Tente novamente.");
        setPending(false);
        return;
      }
      window.location.reload();
    } catch {
      setError("Não foi possível gerar a estratégia. Tente novamente.");
      setPending(false);
    }
  }

  const hasPlan = plan.plan !== null;

  return (
    <div className={styles.wrapper}>
      {hasPlan ? (
        <div className={styles.planBox}>
          <p className={styles.planMeta}>
            Versão {plan.plan_version} — gerado por {plan.plan?.provider ?? "?"}/
            {plan.plan?.model ?? "?"}
          </p>
          {plan.plan?.output ? (
            <dl className={styles.planOutput}>
              <dt>Objetivo</dt>
              <dd>{plan.plan.output.objetivo}</dd>
              <dt>Funil</dt>
              <dd>{plan.plan.output.funil}</dd>
              <dt>Canais</dt>
              <dd>{plan.plan.output.canais.join(", ")}</dd>
              <dt>Justificativa</dt>
              <dd>{plan.plan.output.justificativa}</dd>
            </dl>
          ) : null}
        </div>
      ) : (
        <p className={styles.emptyNote}>Nenhuma estratégia gerada ainda para esta campanha.</p>
      )}

      <label className={styles.field}>
        <span>Ajustes para a próxima geração (opcional)</span>
        <textarea
          rows={2}
          maxLength={2000}
          value={adjustments}
          onChange={(event) => setAdjustments(event.target.value)}
          disabled={pending}
        />
      </label>

      <Button onClick={handleGenerate} disabled={pending}>
        {pending ? "Gerando…" : hasPlan ? "Regenerar estratégia" : "Gerar estratégia"}
      </Button>
      {error ? (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
