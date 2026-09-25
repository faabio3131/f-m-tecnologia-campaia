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
        description="Fundação de autenticação real (Etapa 2 / WP-02 Web). Sem KPIs inventados — os módulos de negócio ainda não foram construídos."
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
          title="Próximos módulos (ainda não construídos nesta etapa)"
          items={[
            { label: "Onboarding e Brand Kit", value: "TARGET — WP-04" },
            { label: "Briefing, estratégia e aprovação", value: "TARGET — WP-05" },
            { label: "Publicação, métricas, billing", value: "TARGET — Etapas futuras" },
          ]}
        />
      </Card>
    </PageContainer>
  );
}
