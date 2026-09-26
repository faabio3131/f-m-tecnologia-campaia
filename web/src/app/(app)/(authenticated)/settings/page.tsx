"use client";

import { Card } from "../../../../components/Card";
import { PageContainer } from "../../../../components/PageContainer";
import { PageHeader } from "../../../../components/PageHeader";
import { StatusPanel } from "../../../../components/StatusPanel";
import { TenantSwitcher } from "../../../../components/TenantSwitcher";
import { useAuth } from "../../../../providers/AuthProvider";
import styles from "./page.module.css";

export default function SettingsPage() {
  const { session } = useAuth();

  return (
    <PageContainer>
      <PageHeader title="Configurações" />
      <Card>
        <StatusPanel
          title="Tenant e unidade de negócio atuais"
          items={[
            { label: "Tenant", value: session?.tenant_id ?? "—" },
            {
              label: "Unidade de negócio",
              value: session?.business_unit_id ?? "todas as unidades do tenant",
            },
          ]}
        />
      </Card>
      <Card>
        <h2 className={styles.sectionTitle}>Trocar de tenant/unidade</h2>
        <p className={styles.sectionDescription}>
          Vínculos reais desta conta (GET /me/memberships). A troca é validada pelo
          backend — só é possível trocar para um vínculo que já pertence a esta
          identidade (POST /auth/session/switch).
        </p>
        <TenantSwitcher />
      </Card>
    </PageContainer>
  );
}
