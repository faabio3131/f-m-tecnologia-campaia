"use client";

import { useEffect, useState } from "react";
import type { ApprovalRequest, Campaign } from "../contracts/types";
import { ApiClientError, api } from "../lib/api/client";
import { Button } from "./Button";
import { Card } from "./Card";
import { Input } from "./Input";
import styles from "./BudgetPanel.module.css";

const STEP_UP_HEADER = { "x-step-up-token": "web-ui-confirmacao-explicita" };

/**
 * WP-06 (26/09/2026, reconciliação PR#6): alteração de orçamento.
 *
 * Reconstruído sobre a arquitetura Web da PR #5 (Etapa 2), não copiado da PR #6 --
 * ver docs/evidence/RECONCILIACAO_TAKEOVER_FINAL_20260926.md. As duas rotas de
 * backend usadas aqui (`PATCH /campaigns/{id}/budget`, `POST /approvals`) já
 * existiam antes deste bloco; este componente só constrói a camada Web sobre elas,
 * reutilizando a mesma fila de aprovação da tela de Aprovações (WP-05) -- quem
 * propõe a mudança de orçamento não decide a própria proposta, a decisão continua
 * acontecendo em /approvals, nunca aqui.
 *
 * `total_amount`/`daily_cap`/`spent_to_date` chegam da API como STRING (Decimal do
 * pydantic v2 serializa assim -- contrato corrigido nesta mesma reconciliação para
 * refletir isso). Este componente sempre normaliza com `Number(...)` antes de
 * comparar ou formatar, para não depender de qual dos dois tipos chega.
 */

function toNumber(value: string | number | undefined | null): number | null {
  if (value === undefined || value === null) return null;
  const n = Number(value);
  return Number.isNaN(n) ? null : n;
}

function formatCurrency(value: number, currency: string): string {
  try {
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(value);
  } catch {
    return `${currency} ${value.toFixed(2)}`;
  }
}

export interface BudgetPanelProps {
  campaignId: string;
  budget: Campaign["budget"];
  /**
   * Achado do E2E cross-stack desta reconciliação (26/09/2026): `budget` é uma prop
   * (snapshot buscado pela página pai em `GET /campaigns/{id}`), nunca refeita por este
   * componente sozinho -- sem isto, depois de um `PATCH /campaigns/{id}/budget` bem
   * sucedido o valor exibido continuava mostrando o orçamento antigo até um reload
   * completo da página, mesmo com o backend real já tendo aplicado a mudança
   * (confirmado com o teste "propor -> aprovar -> aplicar" falhando antes desta
   * correção). A página pai já tem `loadCampaignAndPlan()`; este callback só a aciona
   * de novo depois de aplicar, mesmo padrão já usado por `handleValidate`/
   * `handleGeneratePlan` na própria página.
   */
  onApplied?: () => void | Promise<void>;
}

export function BudgetPanel({ campaignId, budget, onApplied }: BudgetPanelProps) {
  const [pendingApproval, setPendingApproval] = useState<ApprovalRequest | null>(null);
  const [proposedValue, setProposedValue] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function pickRelevant(all: ApprovalRequest[]): ApprovalRequest | null {
    const relevant = all
      .filter((a) => a.campaign_id === campaignId && a.kind === "BUDGET_CHANGE")
      .filter((a) => a.status === "PENDING" || a.status === "APPROVED")
      .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
    return relevant[0] ?? null;
  }

  async function reloadRelevantApproval() {
    try {
      const all = await api.get<ApprovalRequest[]>("/approvals");
      setPendingApproval(pickRelevant(all));
    } catch (err) {
      setLoadError(
        err instanceof ApiClientError ? err.message : "Falha ao carregar aprovações de orçamento.",
      );
    }
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const all = await api.get<ApprovalRequest[]>("/approvals");
        if (active) setPendingApproval(pickRelevant(all));
      } catch (err) {
        if (active) {
          setLoadError(
            err instanceof ApiClientError
              ? err.message
              : "Falha ao carregar aprovações de orçamento.",
          );
        }
      }
    })();
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId]);

  async function handlePropose() {
    setActionError(null);
    const amount = toNumber(proposedValue);
    if (amount === null || amount <= 0) {
      setActionError("Informe um novo valor de orçamento diário válido.");
      return;
    }
    setBusy(true);
    try {
      const result = await api.post<ApprovalRequest>(
        "/approvals",
        { campaign_id: campaignId, kind: "BUDGET_CHANGE", amount: proposedValue },
        { idempotencyKey: `budget-propose-${campaignId}-${crypto.randomUUID()}` },
      );
      setPendingApproval(result);
      setProposedValue("");
    } catch (err) {
      setActionError(
        err instanceof ApiClientError ? err.message : "Falha ao propor a mudança de orçamento.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleApply() {
    if (!pendingApproval || pendingApproval.amount === undefined || pendingApproval.amount === null) {
      return;
    }
    setActionError(null);
    setBusy(true);
    try {
      await api.patch(
        `/campaigns/${campaignId}/budget`,
        { approval_id: pendingApproval.id, daily_cap: pendingApproval.amount },
        {
          headers: STEP_UP_HEADER,
          idempotencyKey: `budget-apply-${pendingApproval.id}`,
        },
      );
      await reloadRelevantApproval();
      await onApplied?.();
    } catch (err) {
      setActionError(
        err instanceof ApiClientError ? err.message : "Falha ao aplicar a mudança de orçamento.",
      );
    } finally {
      setBusy(false);
    }
  }

  const currency = budget?.currency ?? "BRL";
  const dailyCap = toNumber(budget?.daily_cap);
  const totalAmount = toNumber(budget?.total_amount);
  const spentToDate = toNumber(budget?.spent_to_date);

  return (
    <Card>
      <h2 className={styles.sectionTitle}>Orçamento</h2>

      {loadError ? <p className={styles.error}>{loadError}</p> : null}

      <dl className={styles.summary}>
        <div>
          <dt>Diário atual</dt>
          <dd data-testid="budget-daily-cap">
            {dailyCap === null ? "—" : formatCurrency(dailyCap, currency)}
          </dd>
        </div>
        <div>
          <dt>Total da campanha</dt>
          <dd>{totalAmount === null ? "—" : formatCurrency(totalAmount, currency)}</dd>
        </div>
        <div>
          <dt>Gasto até agora</dt>
          <dd>{spentToDate === null ? "—" : formatCurrency(spentToDate, currency)}</dd>
        </div>
      </dl>

      {actionError ? <p className={styles.error}>{actionError}</p> : null}

      {pendingApproval ? (
        pendingApproval.status === "APPROVED" ? (
          <div className={styles.pendingBox}>
            <p>
              Mudança aprovada para{" "}
              {toNumber(pendingApproval.amount) !== null
                ? formatCurrency(toNumber(pendingApproval.amount) as number, currency)
                : pendingApproval.amount}{" "}
              — pronta para aplicar.
            </p>
            <Button disabled={busy} onClick={handleApply}>
              Aplicar alteração
            </Button>
          </div>
        ) : (
          <p className={styles.muted}>
            Pedido de mudança de orçamento pendente — decida na fila de{" "}
            <a href="/approvals">Aprovações</a>.
          </p>
        )
      ) : (
        <div className={styles.proposeBox}>
          <Input
            label="Novo orçamento diário"
            type="number"
            min="0"
            step="0.01"
            value={proposedValue}
            onChange={(e) => setProposedValue(e.target.value)}
            disabled={busy}
          />
          <Button disabled={busy} onClick={handlePropose}>
            Propor mudança de orçamento
          </Button>
        </div>
      )}
    </Card>
  );
}
