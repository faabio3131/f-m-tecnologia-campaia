"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CreativeProposalsPanel } from "@/components/CreativeProposalsPanel";
import { GeneratedImagesPanel } from "@/components/GeneratedImagesPanel";
import { CampaignBrandSnapshot } from "@/components/CampaignBrandSnapshot";
import { useAuth } from "@/providers/AuthProvider";
import { StrategyGenerateButton } from "@/components/StrategyGenerateButton";
import { BudgetPanel } from "../../../../../components/BudgetPanel";
import { Button } from "../../../../../components/Button";
import { Card } from "../../../../../components/Card";
import { ErrorState } from "../../../../../components/ErrorState";
import { InsightsPanel } from "../../../../../components/InsightsPanel";
import { KillSwitchPanel } from "../../../../../components/KillSwitchPanel";
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
 *
 * WP-06 (26/09/2026, reconciliação PR#6): painel de orçamento (`BudgetPanel`) --
 * comportamento portado da PR #6 e reconstruído sobre esta arquitetura Web, não
 * copiado. Ver `docs/evidence/RECONCILIACAO_TAKEOVER_FINAL_20260926.md`.
 *
 * WP-08 (26/09/2026, reconciliação PR#6): parada de emergência desta campanha
 * (`KillSwitchPanel`, escopo CAMPAIGN) -- mesma reconciliação, mesma disciplina.
 *
 * WP-11 (26/09/2026, reconciliação PR#6): métricas desta campanha (`InsightsPanel`,
 * `GET /campaigns/{id}/insights`) -- mesma reconciliação, mesma disciplina de nunca
 * fabricar dados quando a camada de analytics real ainda não existe.
 */
export default function CampaignDetailPage() {
  const params = useParams<{ campaignId: string }>();
  const { me, session } = useAuth();
  const scope = [session?.tenant_id, session?.user_id, me?.business_unit_id, params.campaignId].join(":");
  return <CampaignDetailContent key={scope} campaignId={params.campaignId} />;
}
function CampaignDetailContent({ campaignId }: { campaignId: string }) {
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [decision, setDecision] = useState<PolicyDecision | null>(null);
  const [approval, setApproval] = useState<ApprovalRequest | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showProposals, setShowProposals] = useState(false);

  async function contentDelivered() {
    setDecision(null); setApproval(null);
    await loadCampaignAndPlan();
  }

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

  async function handleValidate() {
    setActionError(null);
    setBusy(true);
    try {
      const result = await api.post<PolicyDecision>(
        `/campaigns/${campaignId}/validate`,
        undefined,
        {
          idempotencyKey: `campaign-validate-${campaignId}-${crypto.randomUUID()}`,
        },
      );
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

      <BudgetPanel
        campaignId={campaignId}
        budget={campaign.budget}
        onApplied={loadCampaignAndPlan}
      />

      {campaign.brief?.brand_snapshot_v1 ? <CampaignBrandSnapshot key={campaignId} snapshot={campaign.brief.brand_snapshot_v1} /> : null}

      <Card>
        <h2 className={styles.sectionTitle}>Estratégia (IA)</h2>
        {plan?.plan ? (
          <pre className={styles.planOutput}>{JSON.stringify(plan.plan, null, 2)}</pre>
        ) : (
          <p className={styles.muted}>Nenhuma estratégia gerada ainda.</p>
        )}
        <StrategyGenerateButton key={campaignId} campaignId={campaignId} hasPlan={Boolean(plan?.plan)}
          busy={busy} onBusy={setBusy} onError={setActionError} onGenerated={contentDelivered} />
      </Card>

      <GeneratedImagesPanel campaignId={campaignId} planVersion={plan?.plan_version ?? 0} />

      <Button variant="secondary" disabled={busy} onClick={() => setShowProposals(true)}>Abrir textos e públicos</Button>
      {showProposals ? <CreativeProposalsPanel campaignId={campaignId} planVersion={plan?.plan_version ?? 0}
        channels={campaign.channels ?? []}
        product={typeof campaign.brief?.product === "string" ? campaign.brief.product : ""}
        audience={typeof campaign.brief?.audience === "string" ? campaign.brief.audience : ""}
        busy={busy} onBusy={setBusy} onDelivered={contentDelivered} /> : null}

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

      <KillSwitchPanel
        scope="CAMPAIGN"
        targetId={campaignId}
        title="Parada de emergência (esta campanha)"
        description="Pausa apenas esta campanha, imediatamente -- sem fila de aprovação e sem step-up (só reduz efeito, nunca amplia). Só funciona se a campanha já estiver num estado ativo/publicado; uma campanha ainda em rascunho não tem o que pausar."
        confirmLabel="Parar esta campanha agora"
        onTriggered={loadCampaignAndPlan}
      />

      <InsightsPanel campaignId={campaignId} />

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
