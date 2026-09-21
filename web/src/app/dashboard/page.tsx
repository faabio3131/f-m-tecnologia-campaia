import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { LogoutButton } from "@/components/LogoutButton";
import { PageContainer } from "@/components/PageContainer";
import { StatusPanel } from "@/components/StatusPanel";
import { TenantSwitcher } from "@/components/TenantSwitcher";
import {
  getPublicBffOrigin,
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
        <EmptyState
          title="Nenhuma funcionalidade de negócio ainda"
          description="O shell autenticado (WP-03) resolve tenant/unidade a partir da sessão e permite trocar de tenant. Onboarding, Brand Kit, campanhas e demais telas de produto chegam a partir do WP-04."
        />
      </Card>
    </PageContainer>
  );
}
