"use client";

import { useState } from "react";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import type { Campaign, KillSwitchResult } from "@/contracts/types";
import styles from "./KillSwitchPanel.module.css";

/**
 * WP-08: twelfth deliberate client-side network call in web/src -- see
 * scripts/lib/security-boundaries.mjs's NETWORK_CALL_ALLOWED_FILES. Same CSRF discipline as
 * every other mutation in this app.
 *
 * Calls POST /kill-switch directly -- unlike every prior WP-05/06/07 mutation, this one does
 * NOT go through the approval queue, because the domain itself dispenses with it: kill switch
 * only ever reduces effect, never widens it (campaia_core/states.py Campaign.apply_kill_switch),
 * so there is nothing for a second human to approve. Also unlike every other sensitive mutation
 * in this app, it sends NO X-Step-Up-Token: Permission.KILL_SWITCH is deliberately outside
 * REQUIRES_STEP_UP in backend/campaia_core/permissions.py -- an emergency stop must not wait on
 * reauthentication. An Idempotency-Key is still required, same discipline as every other
 * mutation.
 *
 * The real /kill-switch endpoint accepts 5 scopes (CAMPAIGN, ACCOUNT, TENANT, PLATFORM, GLOBAL).
 * This panel exposes only CAMPAIGN and TENANT -- a deliberate Web-side scope reduction, not a
 * backend change: GLOBAL crosses tenant boundaries by design (achado 13/17 in
 * routes_campaigns.py), and ACCOUNT/PLATFORM pause every campaign under a connection/channel at
 * once without individual selection. None of the three is appropriate for a regular tenant
 * dashboard without its own explicit product/security decision, which this reconciliation does
 * not make. The API itself still accepts all 5; only this screen narrows the choice.
 *
 * Unlike AutonomyPanel/BudgetPanel, this panel does not reload the page on success -- there is
 * no approval/applied state to re-derive from a fresh server read, and the actually affected
 * campaign ids come back directly in the response body (the real contract gap this WP closed,
 * see contracts/bff-openapi.yaml's KillSwitchResult).
 */
function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|; )campaia_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export interface KillSwitchPanelProps {
  bffOrigin: string;
  campaigns: Campaign[];
}

export function KillSwitchPanel({ bffOrigin, campaigns }: KillSwitchPanelProps) {
  const [scope, setScope] = useState<"CAMPAIGN" | "TENANT">("CAMPAIGN");
  const [campaignId, setCampaignId] = useState(campaigns[0]?.id ?? "");
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<KillSwitchResult | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    setResult(null);

    if (!reason.trim()) {
      setError("Informe o motivo da parada de emergência.");
      setPending(false);
      return;
    }
    if (scope === "CAMPAIGN" && !campaignId) {
      setError("Selecione uma campanha para o escopo CAMPAIGN.");
      setPending(false);
      return;
    }
    const csrfToken = readCsrfCookie();
    if (!csrfToken) {
      setError("Sessão sem cookie CSRF válido — recarregue a página.");
      setPending(false);
      return;
    }

    try {
      const response = await fetch(`${bffOrigin}/kill-switch`, {
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": csrfToken,
          "idempotency-key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          scope,
          target_id: scope === "CAMPAIGN" ? campaignId : null,
          reason: reason.trim(),
        }),
      });
      if (!response.ok) {
        setError("Não foi possível acionar a parada de emergência. Tente novamente.");
        setPending(false);
        return;
      }
      const body = (await response.json()) as KillSwitchResult;
      setResult(body);
      setReason("");
      setPending(false);
    } catch {
      setError("Não foi possível acionar a parada de emergência. Tente novamente.");
      setPending(false);
    }
  }

  return (
    <div className={styles.wrapper}>
      <p className={styles.note}>
        Interrompe o efeito real de uma campanha ou de todas as campanhas do tenant,
        imediatamente, sem passar pela fila de aprovação — a ação só reduz efeito, nunca
        amplia, e fica sempre registrada na auditoria.
      </p>

      <form className={styles.form} onSubmit={handleSubmit}>
        <fieldset className={styles.scopes}>
          <legend>Escopo</legend>
          <label className={styles.scopeOption}>
            <input
              type="radio"
              name="scope"
              value="CAMPAIGN"
              checked={scope === "CAMPAIGN"}
              onChange={() => setScope("CAMPAIGN")}
              disabled={pending}
            />
            Uma campanha
          </label>
          <label className={styles.scopeOption}>
            <input
              type="radio"
              name="scope"
              value="TENANT"
              checked={scope === "TENANT"}
              onChange={() => setScope("TENANT")}
              disabled={pending}
            />
            Todo o tenant
          </label>
        </fieldset>

        {scope === "CAMPAIGN" ? (
          campaigns.length === 0 ? (
            <p className={styles.note}>Nenhuma campanha disponível para este escopo.</p>
          ) : (
            <label className={styles.field}>
              Campanha
              <select
                value={campaignId}
                onChange={(event) => setCampaignId(event.target.value)}
                disabled={pending}
              >
                {campaigns.map((campaign) => (
                  <option key={campaign.id} value={campaign.id}>
                    {campaign.name} ({campaign.id})
                  </option>
                ))}
              </select>
            </label>
          )
        ) : null}

        <label className={styles.field}>
          Motivo
          <input
            type="text"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            disabled={pending}
            maxLength={500}
            placeholder="Ex.: gasto acima do esperado, incidente externo"
          />
        </label>

        <Button type="submit" variant="secondary" disabled={pending}>
          {pending ? "Acionando…" : "Acionar parada de emergência"}
        </Button>
      </form>

      {result ? (
        <div className={styles.result}>
          <Badge tone="neutral">Acionado</Badge>
          <p className={styles.note}>
            Escopo {result.scope} —{" "}
            {result.affected_campaign_ids && result.affected_campaign_ids.length > 0
              ? `campanhas afetadas: ${result.affected_campaign_ids.join(", ")}.`
              : "nenhuma campanha estava em estado pausável."}
          </p>
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
