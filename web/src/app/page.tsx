import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { PageContainer } from "@/components/PageContainer";
import { StatusPanel } from "@/components/StatusPanel";
import { localMeFixture } from "@/fixtures/me.local";
import styles from "./page.module.css";

export default function FoundationPage() {
  const me = localMeFixture;

  return (
    <PageContainer>
      <header className={styles.header}>
        <Badge tone="neutral">CampaIA Web Foundation — WP-01</Badge>
        <h1 className={styles.title}>CampaIA</h1>
        <p className={styles.slogan}>Campanhas inteligentes. Resultados reais.</p>
      </header>

      <Card>
        <Badge tone="warning" role="status">
          Nenhuma sessão, tenant ou integração real está ativa nesta tela.
        </Badge>
        <p className={styles.foundationNote}>
          Esta é a fundação técnica do frontend Web do CampaIA (WP-01), não
          uma funcionalidade comercial concluída. Todos os dados abaixo vêm
          de uma fixture local, derivada do contrato{" "}
          <code>contracts/bff-openapi.yaml</code> — nenhuma chamada de rede é
          feita ao BFF.
        </p>
      </Card>

      <Card>
        <StatusPanel
          title="Estado do scaffold"
          items={[
            { label: "Framework", value: "Next.js (App Router) + React" },
            { label: "TypeScript", value: "Modo estrito" },
            { label: "Origem dos dados", value: "Fixture local (WP-01)" },
            { label: "Autenticação real", value: "Não implementada (WP-02)" },
          ]}
        />
      </Card>

      <Card>
        <StatusPanel
          title="Fixture local (schema Me, contrato bff-openapi.yaml)"
          items={[
            { label: "user_id", value: String(me.user_id) },
            { label: "tenant_id", value: String(me.tenant_id) },
            {
              label: "business_unit_id",
              value: me.business_unit_id ?? "null",
            },
            { label: "roles", value: (me.roles ?? []).join(", ") },
            {
              label: "mfa_enabled",
              value: me.mfa_enabled ? "true" : "false",
            },
          ]}
        />
      </Card>
    </PageContainer>
  );
}
