"use client";

import { useEffect, useState } from "react";
import { Button } from "../../../../components/Button";
import { Card } from "../../../../components/Card";
import { EmptyState } from "../../../../components/EmptyState";
import { ErrorState } from "../../../../components/ErrorState";
import { PageContainer } from "../../../../components/PageContainer";
import { PageHeader } from "../../../../components/PageHeader";
import { Spinner } from "../../../../components/Spinner";
import type { ApprovalRequest } from "../../../../contracts/types";
import { ApiClientError, api } from "../../../../lib/api/client";
import styles from "./page.module.css";

const STEP_UP_HEADER = { "x-step-up-token": "web-ui-confirmacao-explicita" };

/**
 * WP-05 (26/09/2026): fila real de aprovação, `GET /approvals` +
 * `POST /approvals/{id}/decision`. Segregação de funções é decidida 100% pelo
 * backend (`campaia_core.permissions.can_approve`) -- quem propôs a campanha recebe
 * SEPARATION_OF_DUTIES ao tentar decidir aqui, exibido honestamente, nunca escondido
 * ou contornado pela UI.
 */
export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalRequest[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function loadApprovals() {
    try {
      const result = await api.get<ApprovalRequest[]>("/approvals");
      setApprovals(result);
    } catch (err) {
      setLoadError(
        err instanceof ApiClientError ? err.message : "Falha ao carregar aprovações.",
      );
    }
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const result = await api.get<ApprovalRequest[]>("/approvals");
        if (active) setApprovals(result);
      } catch (err) {
        if (active) {
          setLoadError(
            err instanceof ApiClientError ? err.message : "Falha ao carregar aprovações.",
          );
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  async function handleDecision(approvalId: string, decision: "APPROVE" | "REJECT") {
    setActionError(null);
    setBusyId(approvalId);
    try {
      await api.post(
        `/approvals/${approvalId}/decision`,
        { decision },
        {
          headers: STEP_UP_HEADER,
          idempotencyKey: `approval-decision-${approvalId}-${crypto.randomUUID()}`,
        },
      );
      await loadApprovals();
    } catch (err) {
      setActionError(
        err instanceof ApiClientError ? err.message : "Falha ao registrar a decisão.",
      );
    } finally {
      setBusyId(null);
    }
  }

  return (
    <PageContainer>
      <PageHeader
        title="Aprovações"
        description="A segregação de funções é aplicada pelo backend — quem propôs a campanha nunca pode aprovar a própria proposta."
      />

      {loadError ? <ErrorState title="Não foi possível carregar" description={loadError} /> : null}
      {actionError ? <ErrorState title="Não foi possível decidir" description={actionError} /> : null}

      {approvals === null && !loadError ? <Spinner label="Carregando aprovações" /> : null}

      {approvals !== null ? (
        approvals.length === 0 ? (
          <EmptyState title="Nenhuma aprovação pendente" />
        ) : (
          <div className={styles.list}>
            {approvals.map((approval) => (
              <Card key={approval.id} className={styles.card}>
                <p className={styles.itemTitle}>
                  Campanha {approval.campaign_id} — {approval.reason || approval.kind}
                </p>
                <p className={styles.itemDetail}>
                  Status: {approval.status} · Solicitado por: {approval.requested_by}
                </p>
                {approval.status === "PENDING" ? (
                  <div className={styles.actions}>
                    <Button
                      disabled={busyId !== null}
                      onClick={() => handleDecision(approval.id, "APPROVE")}
                      data-testid={`approve-${approval.id}`}
                    >
                      Aprovar
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={busyId !== null}
                      onClick={() => handleDecision(approval.id, "REJECT")}
                      data-testid={`reject-${approval.id}`}
                    >
                      Rejeitar
                    </Button>
                  </div>
                ) : null}
              </Card>
            ))}
          </div>
        )
      ) : null}
    </PageContainer>
  );
}
