"use client";

import { useState } from "react";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import type { ApprovalRequest, AutonomySettings, Campaign } from "@/contracts/types";
import styles from "./AutonomyPanel.module.css";

/**
 * WP-07: eleventh deliberate client-side network call in web/src -- see
 * scripts/lib/security-boundaries.mjs's NETWORK_CALL_ALLOWED_FILES. Same CSRF discipline as
 * every other mutation in this app.
 *
 * Reuses WP-05's approval machinery entirely: proposing a level creates a PENDING
 * ApprovalRequest (POST /approvals, kind: AUTONOMY_CHANGE, amount: the proposed level,
 * carried the same way BudgetPanel.tsx carries a proposed daily_cap) -- deciding it happens
 * on the existing /approvals queue, no new screen. Applying (PUT /autonomy) takes `level`
 * explicitly in its own request body rather than re-deriving it from the approval -- the
 * approval's `amount` is what this panel reads back to know what to send, a real backend
 * design choice, not a bug.
 *
 * POST /approvals requires campaign_id for every kind, including AUTONOMY_CHANGE, even
 * though autonomy is a tenant-wide setting (backend/api/routes_approvals.py) -- this real
 * backend constraint means proposing needs at least one existing campaign; without one, the
 * form is honestly disabled rather than fabricating a campaign or bypassing the API.
 *
 * Levels above `max_level_allowed` (the contracted ceiling, campaia_core/autonomy.py
 * AutonomySettings.__post_init__) are shown but disabled -- the domain itself refuses them
 * (self-promotion guard, invariant I-11), never silently hidden or worked around here.
 */
function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|; )campaia_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

const STEP_UP_MARKER = "web-ui-apply-autonomy-change-button-clicked";

const LEVELS: { value: number; label: string }[] = [
  { value: 0, label: "ASSISTENTE" },
  { value: 1, label: "APROVADO" },
  { value: 2, label: "LIMITADO" },
  { value: 3, label: "OPERACIONAL" },
];

export interface AutonomyPanelProps {
  bffOrigin: string;
  autonomy: AutonomySettings;
  approvals: ApprovalRequest[];
  campaigns: Campaign[];
}

export function AutonomyPanel({ bffOrigin, autonomy, approvals, campaigns }: AutonomyPanelProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [proposedLevel, setProposedLevel] = useState(String(autonomy.level ?? 1));

  const autonomyApprovals = approvals.filter((a) => a.kind === "AUTONOMY_CHANGE");
  const pendingApproval = autonomyApprovals.find((a) => a.status === "PENDING");
  const approvedUnapplied = autonomyApprovals.find(
    (a) =>
      a.status === "APPROVED" &&
      a.amount !== null &&
      a.amount !== undefined &&
      Number(a.amount) !== Number(autonomy.level),
  );
  const firstCampaignId = campaigns[0]?.id;

  async function handlePropose(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    const csrfToken = readCsrfCookie();
    if (!csrfToken) {
      setError("Sessão sem cookie CSRF válido — recarregue a página.");
      setPending(false);
      return;
    }
    if (!firstCampaignId) {
      setError("É necessário ter ao menos uma campanha para propor uma alteração de autonomia.");
      setPending(false);
      return;
    }

    try {
      const response = await fetch(`${bffOrigin}/approvals`, {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json", "x-csrf-token": csrfToken },
        body: JSON.stringify({
          campaign_id: firstCampaignId,
          kind: "AUTONOMY_CHANGE",
          amount: Number(proposedLevel),
        }),
      });
      if (!response.ok) {
        setError("Não foi possível propor a alteração de autonomia. Tente novamente.");
        setPending(false);
        return;
      }
      window.location.reload();
    } catch {
      setError("Não foi possível propor a alteração de autonomia. Tente novamente.");
      setPending(false);
    }
  }

  async function handleApply() {
    if (!approvedUnapplied || approvedUnapplied.amount === null || approvedUnapplied.amount === undefined) {
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
      const response = await fetch(`${bffOrigin}/autonomy`, {
        method: "PUT",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": csrfToken,
          "x-step-up-token": STEP_UP_MARKER,
          "idempotency-key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          level: Number(approvedUnapplied.amount),
          approval_id: approvedUnapplied.id,
        }),
      });
      if (!response.ok) {
        setError("Não foi possível aplicar a alteração de autonomia. Tente novamente.");
        setPending(false);
        return;
      }
      window.location.reload();
    } catch {
      setError("Não foi possível aplicar a alteração de autonomia. Tente novamente.");
      setPending(false);
    }
  }

  return (
    <div className={styles.wrapper}>
      <dl className={styles.summary}>
        <dt>Nível atual</dt>
        <dd>
          {autonomy.level} — {autonomy.level_label}
        </dd>
        <dt>Teto contratado</dt>
        <dd>{autonomy.max_level_allowed}</dd>
      </dl>

      {autonomy.always_require_human && autonomy.always_require_human.length > 0 ? (
        <div className={styles.alwaysHuman}>
          <p className={styles.note}>Sempre exigem aprovação humana, em qualquer nível:</p>
          <ul>
            {autonomy.always_require_human.map((trigger) => (
              <li key={trigger}>{trigger}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {approvedUnapplied ? (
        <div className={styles.actionBox}>
          <Badge tone="accent">Aprovado</Badge>
          <p className={styles.note}>Novo nível aprovado: {approvedUnapplied.amount}.</p>
          <Button onClick={handleApply} disabled={pending}>
            {pending ? "Aplicando…" : "Aplicar alteração"}
          </Button>
        </div>
      ) : pendingApproval ? (
        <div className={styles.actionBox}>
          <Badge tone="neutral">Pendente</Badge>
          <p className={styles.note}>
            Alteração para o nível {pendingApproval.amount} aguardando aprovação.
          </p>
        </div>
      ) : !firstCampaignId ? (
        <p className={styles.note}>
          É necessário ter ao menos uma campanha para propor uma alteração de autonomia.
        </p>
      ) : (
        <form className={styles.form} onSubmit={handlePropose}>
          <fieldset className={styles.levels}>
            <legend>Propor novo nível</legend>
            {LEVELS.map((level) => (
              <label key={level.value} className={styles.levelOption}>
                <input
                  type="radio"
                  name="level"
                  value={level.value}
                  checked={proposedLevel === String(level.value)}
                  onChange={(event) => setProposedLevel(event.target.value)}
                  disabled={pending || level.value > (autonomy.max_level_allowed ?? 1)}
                />
                {level.value} — {level.label}
                {level.value > (autonomy.max_level_allowed ?? 1) ? " (acima do teto contratado)" : ""}
              </label>
            ))}
          </fieldset>
          <Button type="submit" disabled={pending}>
            {pending ? "Enviando…" : "Propor alteração"}
          </Button>
        </form>
      )}

      {error ? (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
