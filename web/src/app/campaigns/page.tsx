import { Badge } from "@/components/Badge";
import { BriefForm } from "@/components/BriefForm";
import { Card } from "@/components/Card";
import { ErrorState } from "@/components/ErrorState";
import { PageContainer } from "@/components/PageContainer";
import { getPublicBffOrigin, getServerCampaigns, getServerSession } from "@/lib/session";
import styles from "./page.module.css";

/**
 * WP-05: entrada da jornada crítica (briefing -> estratégia -> validação -> aprovação),
 * conforme docs/web/06_ROADMAP_WORK_PACKAGES.md WP-05. Lista campanhas existentes (GET
 * /campaigns) e permite submeter um novo briefing (POST /briefs), que cria a campanha em
 * DRAFT -- a geração de estratégia (plano) e a validação acontecem na tela de detalhe
 * (/campaigns/[campaignId]), nunca aqui.
 */
export default async function CampaignsPage() {
  const bffOrigin = getPublicBffOrigin();

  if (!bffOrigin) {
    return (
      <PageContainer>
        <Card>
          <ErrorState
            title="Não configurado"
            description="A variável de ambiente NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN não está definida — a tela de campanhas não sabe onde está o backend (BFF)."
          />
        </Card>
      </PageContainer>
    );
  }

  const me = await getServerSession();
  if (!me) {
    const loginUrl = `${bffOrigin}/auth/login?redirect_after_login=${encodeURIComponent("/campaigns")}`;
    return (
      <PageContainer>
        <header className={styles.header}>
          <Badge tone="neutral">CampaIA Web — Campanhas (WP-05)</Badge>
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

  const campaigns = await getServerCampaigns();
  if (campaigns === null) {
    return (
      <PageContainer>
        <Card>
          <ErrorState
            title="Não foi possível carregar as campanhas"
            description="GET /campaigns falhou apesar de uma sessão válida existir. Tente recarregar a página."
          />
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <header className={styles.header}>
        <Badge tone="accent">CampaIA Web — Campanhas (WP-05)</Badge>
        <h1 className={styles.title}>Campanhas</h1>
      </header>

      <Card>
        <h2 className={styles.sectionTitle}>Novo briefing</h2>
        <BriefForm bffOrigin={bffOrigin} />
      </Card>

      <Card>
        <h2 className={styles.sectionTitle}>Campanhas existentes</h2>
        {campaigns.length === 0 ? (
          <p className={styles.emptyNote}>Nenhuma campanha ainda — submeta o primeiro briefing acima.</p>
        ) : (
          <ul className={styles.campaignList}>
            {campaigns.map((campaign) => (
              <li key={campaign.id} className={styles.campaignItem}>
                <a href={`/campaigns/${campaign.id}`} className={styles.campaignLink}>
                  <strong>{campaign.name || campaign.objective}</strong>
                  <Badge tone="neutral">{campaign.state}</Badge>
                </a>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </PageContainer>
  );
}
