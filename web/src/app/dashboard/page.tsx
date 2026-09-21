import Link from "next/link";
import { AutonomyPanel } from "@/components/AutonomyPanel";
import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { ErrorState } from "@/components/ErrorState";
import { KillSwitchPanel } from "@/components/KillSwitchPanel";
import { LogoutButton } from "@/components/LogoutButton";
import { PageContainer } from "@/components/PageContainer";
import { StatusPanel } from "@/components/StatusPanel";
import { TenantSwitcher } from "@/components/TenantSwitcher";
import {
  getPublicBffOrigin,
  getServerApprovals,
  getServerAutonomy,
  getServerCampaigns,
  getServerSession,
  getServerSessionMemberships,
} from "@/lib/session";
import styles from "./page.module.css";

/**
 * WP-03: shell autenticado do dashboard. Tenant/unidade ativos vêm exclusivamente da
 * sessão real (GET /me, GET /session/memberships) -- nunca de um header ou parâmetro
 * client-supplied. Nenhuma funcionalidade de negócio vive aqui (fora do escopo do WP-03,
 * ver roadmap) -- apenas navegação: identidade, troca de tenant e um placeholder
 * explicitamente rotulado como vazio até o WP-04 em diante preencher esta área.
 */
export default async function DashboardPage() {
  const bffOrigin = getPublicBffOrigin();

  if (!bffOrigin) {
    return (
      <PageContainer>
        <Card>
          <ErrorState
            title="Não configurado"
            description="A variável de ambiente NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN não está definida — o shell autenticado não sabe onde está o backend (BFF)."
          />
        </Card>
      </PageContainer>
    );
  }

  const me = await getServerSession();

  if (!me) {
    const loginUrl = `${bffOrigin}/auth/login?redirect_after_login=${encodeURIComponent("/dashboard")}`;
    return (
      <PageContainer>
        <header className={styles.header}>
          <Badge tone="neutral">CampaIA Web — Dashboard (WP-03)</Badge>
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

  const memberships = await getServerSessionMemberships();

  if (!memberships) {
    return (
      <PageContainer>
        <Card>
          <ErrorState
            title="Não foi possível carregar os memberships da sessão"
            description="GET /session/memberships falhou apesar de uma sessão válida existir. Tente recarregar a página."
          />
        </Card>
      </PageContainer>
    );
  }

  const [autonomy, approvals, campaigns] = await Promise.all([
    getServerAutonomy(),
    getServerApprovals(),
    getServerCampaigns(),
  ]);

  return (
    <PageContainer>
      <header className={styles.header}>
        <Badge tone="accent">CampaIA Web — Dashboard (WP-03)</Badge>
        <h1 className={styles.title}>{me.tenant_id}</h1>
      </header>
      <Card>
        <div className={styles.identityRow}>
          <StatusPanel
            title="Sessão ativa"
            items={[
              { label: "user_id", value: me.user_id ?? "" },
              { label: "tenant_id", value: me.tenant_id ?? "" },
              { label: "business_unit_id", value: me.business_unit_id ?? "null" },
              { label: "roles", value: (me.roles ?? []).join(", ") },
            ]}
          />
          <TenantSwitcher bffOrigin={bffOrigin} memberships={memberships.memberships ?? []} />
        </div>
        <LogoutButton bffOrigin={bffOrigin} />
      </Card>
      <Card>
        <h2 className={styles.navTitle}>Onboarding e campanhas</h2>
        <nav className={styles.nav}>
          <Link className={styles.navLink} href="/onboarding">
            Onboarding (Brand Kit, conectar contas)
          </Link>
          <Link className={styles.navLink} href="/campaigns">
            Campanhas (briefing, estratégia, validação)
          </Link>
          <Link className={styles.navLink} href="/approvals">
            Fila de aprovação
          </Link>
        </nav>
      </Card>

      <Card>
        <h2 className={styles.navTitle}>Nível de autonomia</h2>
        {autonomy === null || approvals === null || campaigns === null ? (
          <ErrorState
            title="Não foi possível carregar o nível de autonomia"
            description="GET /autonomy, GET /approvals ou GET /campaigns falhou. Tente recarregar a página."
          />
        ) : (
          <AutonomyPanel
            bffOrigin={bffOrigin}
            autonomy={autonomy}
            approvals={approvals}
            campaigns={campaigns}
          />
        )}
      </Card>

      <Card>
        <h2 className={styles.navTitle}>Parada de emergência</h2>
        {campaigns === null ? (
          <ErrorState
            title="Não foi possível carregar as campanhas"
            description="GET /campaigns falhou. Tente recarregar a página."
          />
        ) : (
          <KillSwitchPanel bffOrigin={bffOrigin} campaigns={campaigns} />
        )}
      </Card>
    </PageContainer>
  );
}
