import { EmptyState } from "../../../../components/EmptyState";
import { PageContainer } from "../../../../components/PageContainer";
import { PageHeader } from "../../../../components/PageHeader";

export default function ConnectionsPage() {
  return (
    <PageContainer>
      <PageHeader title="Conexões" />
      <EmptyState
        title="Ainda não implementado"
        description="OAuth real de Google Ads/Meta/WhatsApp está fora do escopo desta etapa — placeholder honesto, não uma funcionalidade simulada."
      />
    </PageContainer>
  );
}
