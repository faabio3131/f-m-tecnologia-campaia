"use client";

import { Card } from "../../../../components/Card";
import { EmptyState } from "../../../../components/EmptyState";
import { PageContainer } from "../../../../components/PageContainer";
import { PageHeader } from "../../../../components/PageHeader";
import { StatusPanel } from "../../../../components/StatusPanel";
import { useAuth } from "../../../../providers/AuthProvider";

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
        <EmptyState
          title="Troca de tenant/unidade — pendência de contrato"
          description={
            "PENDÊNCIA registrada (Etapa 2, seção 20): multi-tenant/business-unit " +
            "switching precisa de um contrato HTTP específico no backend antes de " +
            "qualquer implementação funcional. O shell está estruturado para receber " +
            "um seletor futuro, mas nenhum seletor falso é renderizado aqui — o " +
            "tenant/unidade exibidos vêm sempre da sessão real, nunca de um valor " +
            "escolhido pelo navegador."
          }
        />
      </Card>
    </PageContainer>
  );
}
