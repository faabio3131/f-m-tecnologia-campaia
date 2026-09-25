import { EmptyState } from "../../../../components/EmptyState";
import { PageContainer } from "../../../../components/PageContainer";
import { PageHeader } from "../../../../components/PageHeader";

export default function CampaignsPage() {
  return (
    <PageContainer>
      <PageHeader title="Campanhas" />
      <EmptyState
        title="Ainda não implementado"
        description="A criação e gestão de campanhas (WP-05) está fora do escopo desta etapa — placeholder honesto, não uma funcionalidade simulada."
      />
    </PageContainer>
  );
}
