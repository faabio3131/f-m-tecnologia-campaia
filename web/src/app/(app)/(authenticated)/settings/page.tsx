"use client";

import { useEffect, useState } from "react";
import { AutonomyPanel } from "../../../../components/AutonomyPanel";
import { Card } from "../../../../components/Card";
import { PageContainer } from "../../../../components/PageContainer";
import { PageHeader } from "../../../../components/PageHeader";
import { StatusPanel } from "../../../../components/StatusPanel";
import { TenantSwitcher } from "../../../../components/TenantSwitcher";
import type { Campaign } from "../../../../contracts/types";
import { api } from "../../../../lib/api/client";
import { useAuth } from "../../../../providers/AuthProvider";
import styles from "./page.module.css";

/**
 * WP-07 (26/09/2026, reconciliação PR#6): nível de autonomia. Ver
 * AutonomyPanel.tsx -- vive aqui, não em campaigns/[campaignId], porque autonomia é
 * configuração de TENANT, não de campanha.
 */
export default function SettingsPage() {
  const { session } = useAuth();
  const [anchorCampaignId, setAnchorCampaignId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const result = await api.get<{ items: Campaign[] }>("/campaigns");
        if (active) setAnchorCampaignId(result.items[0]?.id ?? null);
      } catch {
        // Silencioso de propósito: AutonomyPanel já trata anchorCampaignId === null com
        // uma mensagem honesta própria; uma falha aqui não deve quebrar o resto da
        // página de Configurações (Tenant/TenantSwitcher continuam funcionando).
        if (active) setAnchorCampaignId(null);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

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

      <AutonomyPanel anchorCampaignId={anchorCampaignId} />
    </PageContainer>
  );
}
