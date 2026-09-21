import { Card } from "@/components/Card";
import { LoadingState } from "@/components/LoadingState";
import { PageContainer } from "@/components/PageContainer";

export default function ApprovalsLoading() {
  return (
    <PageContainer>
      <Card>
        <LoadingState label="Carregando aprovações…" />
      </Card>
    </PageContainer>
  );
}
