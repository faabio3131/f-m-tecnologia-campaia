"use client";

import { useState } from "react";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import type { ApprovalRequest, Campaign } from "@/contracts/types";
import styles from "./BudgetPanel.module.css";

/**
 * WP-06: tenth deliberate client-side network call in web/src -- see
 * scripts/lib/security-boundaries.mjs's NETWORK_CALL_ALLOWED_FILES. Same CSRF discipline as
 * every other mutation in this app.
 *
 * Reuses WP-05's approval machinery entirely: proposing a change creates a PENDING
 * ApprovalRequest (POST /approvals, kind: BUDGET_CHANGE, amount: the proposed daily_cap) --
 * deciding it happens on the existing /approvals queue (ApprovalDecisionCard.tsx), no new
 * screen. Once APPROVED, this panel shows an explicit "Aplicar" step (PATCH
 * /campaigns/{id}/budget, CSRF + X-Step-Up-Token + Idempotency-Key) -- approval and
 * application are two distinct real actions, never conflated into one click, matching how
 * the backend itself models them as separate steps.
 *
 * "Applied" is inferred, not a dedicated status: an APPROVED BUDGET_CHANGE approval whose
 * amount already equals the campaign's current daily_cap is treated as already applied (the
 * backend has no separate "applied" flag on ApprovalRequest -- status stays APPROVED
 * forever). This is the same real value the backend itself would compare, not a guess.
 *
 * P-36 fix (missão de reconciliação, 22/09/2026): the contract now correctly types every
 * monetary field here as `string` (decimal-precise, e.g. "500.00"), matching what the
 * backend always actually sent. Every payload this component sends carries the string
 * value through unmodified -- never re-serialized via `Number(...)`, which would round-trip
 * through an IEEE-754 float and risk losing precision on the way back to the backend. The
 * one exception is the `!==` comparison below, which only decides a boolean UI branch
 * (never sent over the wire) and still goes through `Number(...)` for a normalized
 * numeric-equality check (e.g. "500.00" vs "500" would otherwise compare unequal as raw
 * strings despite being the same amount).
 */
function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|; )campaia_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

const STEP_UP_MARKER = "web-ui-apply-budget-change-button-clicked";

export interface BudgetPanelProps {
  bffOrigin: string;
  campaignId: string;
  budget: Campaign["budget"];
  approvals: ApprovalRequest[];
}

export function BudgetPanel({ bffOrigin, campaignId, budget, approvals }: BudgetPanelProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [proposedCap, setProposedCap] = useState("");

  const budgetChangeApprovals = approvals.filter(
    (a) => a.campaign_id === campaignId && a.kind === "BUDGET_CHANGE",
  );
  const pendingApproval = budgetChangeApprovals.find((a) => a.status === "PENDING");
  const approvedUnapplied = budgetChangeApprovals.find(
    (a) =>
      a.status === "APPROVED" &&
      a.amount !== null &&
      a.amount !== undefined &&
      Number(a.amount) !== Number(budget?.daily_cap),
  );

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

    // Validate using a numeric parse, but send the original string the user typed --
    // never a value that passed through Number(...), which would risk precision loss on
    // the wire (P-36 fix).
    if (!Number.isFinite(Number(proposedCap)) || Number(proposedCap) <= 0) {
      setError("Informe um teto diário válido, maior que zero.");
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
          kind: "BUDGET_CHANGE",
          amount: proposedCap,
        }),
      });
      if (!response.ok) {
        setError("Não foi possível propor a alteração de orçamento. Tente novamente.");
        setPending(false);
        return;
      }
      window.location.reload();
    } catch {
      setError("Não foi possível propor a alteração de orçamento. Tente novamente.");
      setPending(false);
    }
  }

  async function handleApply() {
    if (!approvedUnapplied) return;
    setPending(true);
    setError(null);
    const csrfToken = readCsrfCookie();
    if (!csrfToken) {
      setError("Sessão sem cookie CSRF válido — recarregue a página.");
      setPending(false);
      return;
    }

    try {
      const response = await fetch(`${bffOrigin}/campaigns/${encodeURIComponent(campaignId)}/budget`, {
        method: "PATCH",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": csrfToken,
          "x-step-up-token": STEP_UP_MARKER,
          "idempotency-key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          // The original decimal string, never coerced through Number(...) (P-36 fix).
          daily_cap: approvedUnapplied.amount,
          approval_id: approvedUnapplied.id,
        }),
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as
          | { code?: string; message?: string }
          | null;
        setError(
          body?.code === "BUDGET_LIMIT" && body.message
            ? body.message
            : "Não foi possível aplicar a alteração de orçamento. Tente novamente.",
        );
        setPending(false);
        return;
      }
      window.location.reload();
    } catch {
      setError("Não foi possível aplicar a alteração de orçamento. Tente novamente.");
      setPending(false);
    }
  }

  return (
    <div className={styles.wrapper}>
      <dl className={styles.summary}>
        <dt>Orçamento total</dt>
        <dd>
          {budget?.currency} {budget?.total_amount}
        </dd>
        <dt>Teto diário atual</dt>
        <dd>
          {budget?.currency} {budget?.daily_cap}
        </dd>
        <dt>Gasto até o momento</dt>
        <dd>
          {budget?.currency} {budget?.spent_to_date}
        </dd>
      </dl>

      {approvedUnapplied ? (
        <div className={styles.actionBox}>
          <Badge tone="accent">Aprovado</Badge>
          <p className={styles.note}>
            Novo teto diário aprovado: {budget?.currency} {approvedUnapplied.amount}.
          </p>
          <Button onClick={handleApply} disabled={pending}>
            {pending ? "Aplicando…" : "Aplicar alteração"}
          </Button>
        </div>
      ) : pendingApproval ? (
        <div className={styles.actionBox}>
          <Badge tone="neutral">Pendente</Badge>
          <p className={styles.note}>
            Alteração para {budget?.currency} {pendingApproval.amount} aguardando aprovação.
          </p>
        </div>
      ) : (
        <form className={styles.form} onSubmit={handlePropose}>
          <label className={styles.field}>
            <span>Propor novo teto diário</span>
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={proposedCap}
              onChange={(event) => setProposedCap(event.target.value)}
              disabled={pending}
              required
            />
          </label>
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
