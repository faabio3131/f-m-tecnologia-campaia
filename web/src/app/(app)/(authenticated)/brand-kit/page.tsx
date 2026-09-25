import { EmptyState } from "../../../../components/EmptyState";
import { PageContainer } from "../../../../components/PageContainer";
import { PageHeader } from "../../../../components/PageHeader";

export default function BrandKitPage() {
  return (
    <PageContainer>
      <PageHeader title="Brand Kit" />
      <EmptyState
        title="Ainda não implementado"
        description="O onboarding e Brand Kit reais (WP-04) estão fora do escopo desta etapa — placeholder honesto, não uma funcionalidade simulada."
      />
    </PageContainer>
  );
}
