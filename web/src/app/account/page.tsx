import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { LogoutButton } from "@/components/LogoutButton";
import { PageContainer } from "@/components/PageContainer";
import { StatusPanel } from "@/components/StatusPanel";
import { getPublicBffOrigin, getServerSession } from "@/lib/session";
import styles from "./page.module.css";

export default async function AccountPage() {
  const bffOrigin = getPublicBffOrigin();
  const me = bffOrigin ? await getServerSession() : null;

  if (!bffOrigin) {
    return (
      <PageContainer>
        <Card>
          <Badge tone="warning">Não configurado</Badge>
          <p className={styles.note}>
            A variável de ambiente <code>NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN</code> não está
            definida — a fundação Web não sabe onde está o backend (BFF) para iniciar o
            login. Isto é esperado em um checkout limpo do WP-01/WP-02 sem configuração de
            ambiente local.
          </p>
        </Card>
      </PageContainer>
    );
  }

  if (!me) {
    const loginUrl = `${bffOrigin}/auth/login?redirect_after_login=${encodeURIComponent("/account")}`;
    return (
      <PageContainer>
        <header className={styles.header}>
          <Badge tone="neutral">CampaIA Web — Conta (WP-02)</Badge>
          <h1 className={styles.title}>Você não está autenticado</h1>
        </header>
        <Card>
          <p className={styles.note}>
            O login usa OIDC Authorization Code + PKCE real contra o provedor de identidade
            configurado no backend. Nenhum token ou segredo passa por este frontend — a
            sessão é um cookie <code>HttpOnly</code> emitido pelo próprio backend.
          </p>
          <a className={styles.loginLink} href={loginUrl}>
            Entrar
          </a>
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <header className={styles.header}>
        <Badge tone="accent">CampaIA Web — Conta (WP-02)</Badge>
        <h1 className={styles.title}>Sessão real ativa</h1>
      </header>
      <Card>
        <StatusPanel
          title="Sessão (GET /me, sessão real via cookie)"
          items={[
            { label: "user_id", value: me.user_id ?? "" },
            { label: "tenant_id", value: me.tenant_id ?? "" },
            { label: "business_unit_id", value: me.business_unit_id ?? "null" },
            { label: "roles", value: (me.roles ?? []).join(", ") },
            { label: "mfa_enabled", value: me.mfa_enabled ? "true" : "false" },
          ]}
        />
      </Card>
      <Card>
        <LogoutButton bffOrigin={bffOrigin} />
      </Card>
    </PageContainer>
  );
}
