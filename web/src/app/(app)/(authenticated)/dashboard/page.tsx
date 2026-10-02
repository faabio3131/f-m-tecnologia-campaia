"use client";

import { Card } from "../../../../components/Card";
import { PageContainer } from "../../../../components/PageContainer";
import { PageHeader } from "../../../../components/PageHeader";
import { StatusPanel } from "../../../../components/StatusPanel";
import { useAuth } from "../../../../providers/AuthProvider";

export default function DashboardPage() {
  const { session, me } = useAuth();

  if (!session || !me) return null; // guardado pelo layout pai

  return (
    <PageContainer>
      <PageHeader
        title="Dashboard"
        description="Visão segura do tenant autenticado. O CampaIA já possui onboarding, organização, Brand Kit, campanhas e aprovações; métricas externas e operação comercial completa continuam em evolução."
      />
      <Card>
        <StatusPanel
          title="Sessão autenticada"
          items={[
            { label: "Usuário", value: session.user_id },
            { label: "Tenant", value: session.tenant_id },
            {
              label: "Unidade de negócio",
              value: session.business_unit_id ?? "todas as unidades do tenant",
            },
            { label: "Papéis (roles)", value: (me.roles ?? []).join(", ") || "nenhum" },
            { label: "Permissões", value: `${(me.permissions ?? []).length} concedidas` },
            { label: "MFA habilitado", value: me.mfa_enabled ? "sim" : "não" },
          ]}
        />
      </Card>
      <Card>
        <StatusPanel
          title="Estado funcional atual"
          items={[
            {
              label: "Onboarding, organização e Brand Kit",
              value: "IMPLEMENTADO — evolução de assets permanece em F6",
            },
            {
              label: "Briefing, estratégia, policy e aprovação",
              value: "IMPLEMENTADO — criativos/preview completos permanecem em F7",
            },
            {
              label: "Billing",
              value: "PARCIAL — backend F5 implementado; UI comercial e inadimplência pendentes",
            },
            {
              label: "Publicação e métricas reais",
              value: "TARGET — dependem dos conectores oficiais F8–F13",
            },
          ]}
        />
      </Card>
    </PageContainer>
  );
}
