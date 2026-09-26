"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "../../../../../components/Button";
import { Card } from "../../../../../components/Card";
import { ErrorState } from "../../../../../components/ErrorState";
import { PageContainer } from "../../../../../components/PageContainer";
import { PageHeader } from "../../../../../components/PageHeader";
import { Spinner } from "../../../../../components/Spinner";
import type { ApprovalRequest, Campaign, PolicyDecision } from "../../../../../contracts/types";
import { ApiClientError, api } from "../../../../../lib/api/client";
import styles from "./page.module.css";

interface PlanResponse {
  campaign_id: string;
  plan_version: number;
  plan: Record<string, unknown> | null;
}

/**
 * WP-05 (26/09/2026): detalhe real de campanha -- estratégia (IA simulada,
 * `POST /campaigns/{id}/plan/regenerate`), validação (`POST .../validate`, Policy
 * Engine real) e pedido de aprovação (`POST /approvals`). A decisão da aprovação
 * (aprovar/rejeitar) acontece na fila (`/approvals`) -- aqui só se registra o pedido,
 * refletindo a segregação de funções real do backend (quem propõe não decide aqui).
 * Publicação real fica fora de escopo (depende de integração com provider, Fases 5–7).
 */
export default function CampaignDetailPage() {
  const params = useParams<{ campaignId: string }>();
  const campaignId = params.campaignId;

  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [decision, setDecision] = useState<PolicyDecision | null>(null);
  const [approval, setApproval] = useState<ApprovalRequest | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadCampaignAndPlan() {
    try {
      const [campaignResult, planResult] = await Promise.all([
        api.get<Campaign>(`/campaigns/${campaignId}`),
        api.get<PlanResponse>(`/campaigns/${campaignId}/plan`),
      ]);
      setCampaign(campaignResult);
      setPlan(planResult);
    } catch (err) {
      setLoadError(
        err instanceof ApiClientError ? err.message : "Falha ao carregar a campanha.",
      );
    }
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [campaignResult, planResult] = await Promise.all([
          api.get<Campaign>(`/campaigns/${campaignId}`),
          api.get<PlanResponse>(`/campaigns/${campaignId}/plan`),
        ]);
        if (active) {
          setCampaign(campaignResult);
          setPlan(planResult);
        }
      } catch (err) {
        if (active) {
          setLoadError(
            err instanceof ApiClientError ? err.message : "Falha ao carregar a campanha.",
          );
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [campaignId]);

  async function handleGeneratePlan() {
    setActionError(null);
    setBusy(true);
    try {
      await api.post(
        `/campaigns/${campaignId}/plan/regenerate`,
        {},
        { idempotencyKey: `plan-regenerate-${campaignId}-${crypto.randomUUID()}` },
      );
      await loadCampaignAndPlan();
    } catch (err) {
      setActionError(
        err instanceof ApiClientError ? err.message : "Falha ao gerar a estratégia.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleValidate() {
    setActionError(null);
    setBusy(true);
    try {
      const result = await api.post<PolicyDecision>(`/campaigns/${campaignId}/validate`);
      setDecision(result);
      await loadCampaignAndPlan();
    } catch (err) {
      setActionError(
        err instanceof ApiClientError ? err.message : "Falha ao validar a campanha.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleRequestApproval() {
    setActionError(null);
    setBusy(true);
    try {
      const result = await api.post<ApprovalRequest>(
        "/approvals",
        { campaign_id: campaignId, kind: "PUBLISH" },
        { idempotencyKey: `approval-create-${campaignId}-${crypto.randomUUID()}` },
      );
      setApproval(result);
    } catch (err) {
      setActionError(
        err instanceof ApiClientError ? err.message : "Falha ao solicitar aprovação.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (loadError) {
    return (
      <PageContainer>
        <ErrorState title="Não foi possível carregar a campanha" description={loadError} />
      </PageContainer>
    );
  }

  if (campaign === null) {
    return (
      <PageContainer>
        <Spinner label="Carregando campanha" />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <PageHeader
        title={campaign.name || campaign.objective || "Campanha"}
        description={`Estado atual: ${campaign.state}`}
      />

      {actionError ? <ErrorState title="Não foi possível continuar" description={actionError} /> : null}

      <Card>
        <h2 className={styles.sectionTitle}>Estratégia (IA)</h2>
        {plan?.plan ? (
          <pre className={styles.planOutput}>{JSON.stringify(plan.plan, null, 2)}</pre>
        ) : (
          <p className={styles.muted}>Nenhuma estratégia gerada ainda.</p>
        )}
        <Button disabled={busy} onClick={handleGeneratePlan}>
          {plan?.plan ? "Regenerar estratégia" : "Gerar estratégia"}
        </Button>
      </Card>

      <Card>
        <h2 className={styles.sectionTitle}>Validação (Policy Engine)</h2>
        {decision ? (
          <div className={styles.decisionBox}>
            <p className={styles.itemDetail}>Resultado: {decision.outcome}</p>
            {decision.findings.length > 0 ? (
              <ul className={styles.findingsList}>
                {decision.findings.map((finding, i) => (
                  <li key={i}>
                    [{finding.severity}] {finding.explanation}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : (
          <p className={styles.muted}>Campanha ainda não validada.</p>
        )}
        <Button disabled={busy} onClick={handleValidate}>
          Validar campanha
        </Button>
      </Card>

      {decision?.outcome === "APPROVABLE" ? (
        <Card>
          <h2 className={styles.sectionTitle}>Aprovação</h2>
          {approval ? (
            <p className={styles.itemDetail}>
              Pedido criado (status: {approval.status}) — decida na fila de{" "}
              <a href="/approvals">Aprovações</a>.
            </p>
          ) : (
            <p className={styles.muted}>
              Nenhum pedido de aprovação ainda. Quem propõe não pode decidir a própria
              proposta — a decisão acontece na fila de Aprovações, por outro usuário.
            </p>
          )}
          {!approval ? (
            <Button disabled={busy} onClick={handleRequestApproval}>
              Solicitar aprovação para publicar
            </Button>
          ) : null}
        </Card>
      ) : null}
    </PageContainer>
  );
}
