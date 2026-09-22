import { Badge } from "@/components/Badge";
import { BudgetPanel } from "@/components/BudgetPanel";
import { Card } from "@/components/Card";
import { ErrorState } from "@/components/ErrorState";
import { PageContainer } from "@/components/PageContainer";
import { PlanPanel } from "@/components/PlanPanel";
import { ValidationPanel } from "@/components/ValidationPanel";
import {
  getPublicBffOrigin,
  getServerApprovals,
  getServerCampaign,
  getServerInsights,
  getServerPlan,
  getServerSession,
} from "@/lib/session";
import styles from "./page.module.css";

/**
 * WP-05: detalhe da campanha -- estratégia (IA) e validação, os dois passos entre o
 * briefing (/campaigns) e a fila de aprovação (/approvals). Publicação real fica fora do
 * escopo deste Work Package (docs/web/06_ROADMAP_WORK_PACKAGES.md: "depende de adaptador de
 * provider, fora desta lista") -- nada nesta tela chama POST .../publish. WP-11 adiciona a
 * seção "Métricas": o estado real de GET /campaigns/{id}/insights, honestamente vazio hoje
 * (nenhuma camada de analytics em campaia_core ainda) -- exibido diretamente, sem gráfico ou
 * placeholder inventado pela Web.
 */
export default async function CampaignDetailPage({
  params,
}: {
  params: Promise<{ campaignId: string }>;
}) {
  const { campaignId } = await params;
  const bffOrigin = getPublicBffOrigin();

  if (!bffOrigin) {
    return (
      <PageContainer>
        <Card>
          <ErrorState
            title="Não configurado"
            description="A variável de ambiente NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN não está definida — a tela de campanha não sabe onde está o backend (BFF)."
          />
        </Card>
      </PageContainer>
    );
  }

  const me = await getServerSession();
  if (!me) {
    const loginUrl = `${bffOrigin}/auth/login?redirect_after_login=${encodeURIComponent(`/campaigns/${campaignId}`)}`;
    return (
      <PageContainer>
        <header className={styles.header}>
          <Badge tone="neutral">CampaIA Web — Campanha (WP-05)</Badge>
          <h1 className={styles.title}>Você não está autenticado</h1>
        </header>
        <Card>
          <a className={styles.loginLink} href={loginUrl}>
            Entrar
          </a>
        </Card>
      </PageContainer>
    );
  }

  const [campaign, plan, approvals, insights] = await Promise.all([
    getServerCampaign(campaignId),
    getServerPlan(campaignId),
    getServerApprovals(),
    getServerInsights(campaignId),
  ]);

  if (campaign === null || plan === null || approvals === null) {
    return (
      <PageContainer>
        <Card>
          <ErrorState
            title="Não foi possível carregar a campanha"
            description="GET /campaigns/{id}, GET /campaigns/{id}/plan ou GET /approvals falhou, ou esta campanha não existe. Tente recarregar a página."
          />
        </Card>
      </PageContainer>
    );
  }

  // WP-06 introduced a second approval kind (BUDGET_CHANGE) per campaign -- this must only
  // reflect a pending PUBLISH approval, or a pending budget-change request would wrongly
  // disable ValidationPanel's "Solicitar aprovação" button too.
  const hasPendingApproval = approvals.some(
    (approval) =>
      approval.campaign_id === campaignId &&
      approval.status === "PENDING" &&
      approval.kind === "PUBLISH",
  );

  return (
    <PageContainer>
      <header className={styles.header}>
        <Badge tone="accent">CampaIA Web — Campanha (WP-05)</Badge>
        <h1 className={styles.title}>{campaign.name || campaign.objective}</h1>
        <Badge tone="neutral">{campaign.state}</Badge>
      </header>

      <Card>
        <h2 className={styles.sectionTitle}>Briefing</h2>
        <p className={styles.brief}>{campaign.objective}</p>
        <p className={styles.briefMeta}>
          Canais: {(campaign.channels ?? []).join(", ") || "—"} · Orçamento:{" "}
          {campaign.budget?.currency} {campaign.budget?.total_amount} (diário{" "}
          {campaign.budget?.daily_cap})
        </p>
      </Card>

      <Card>
        <h2 className={styles.sectionTitle}>Estratégia (IA)</h2>
        <PlanPanel bffOrigin={bffOrigin} campaignId={campaignId} plan={plan} />
      </Card>

      <Card>
        <h2 className={styles.sectionTitle}>Validação e aprovação</h2>
        <ValidationPanel
          bffOrigin={bffOrigin}
          campaignId={campaignId}
          hasPendingApproval={hasPendingApproval}
        />
      </Card>

      <Card>
        <h2 className={styles.sectionTitle}>Orçamento</h2>
        <BudgetPanel
          bffOrigin={bffOrigin}
          campaignId={campaignId}
          budget={campaign.budget}
          approvals={approvals}
        />
      </Card>

      <Card>
        <h2 className={styles.sectionTitle}>Métricas</h2>
        {insights === null ? (
          <ErrorState
            title="Não foi possível carregar as métricas"
            description="GET /campaigns/{id}/insights falhou. Tente recarregar a página."
          />
        ) : insights.points && insights.points.length > 0 ? (
          <ul className={styles.insightsList}>
            {insights.points.map((point, index) => (
              <li key={index}>
                {point.date} · {point.channel}: {point.impressions} impressões,{" "}
                {point.clicks} cliques, {point.conversions} conversões
              </li>
            ))}
          </ul>
        ) : (
          // `note` is typed optional by the generated contract types (object property with
          // no `required` entry) but always present in the real response -- same pattern as
          // Connection.id/Campaign.id elsewhere in this app.
          <p className={styles.insightsNote}>{insights.note as string}</p>
        )}
      </Card>
    </PageContainer>
  );
}
