import { EmptyState } from "../../../../components/EmptyState";
import { PageContainer } from "../../../../components/PageContainer";
import { PageHeader } from "../../../../components/PageHeader";

export default function ApprovalsPage() {
  return (
    <PageContainer>
      <PageHeader title="Aprovações" />
      <EmptyState
        title="Ainda não implementado"
        description="A fila de aprovação real (WP-05) está fora do escopo desta etapa — placeholder honesto, não uma funcionalidade simulada."
      />
    </PageContainer>
  );
}
