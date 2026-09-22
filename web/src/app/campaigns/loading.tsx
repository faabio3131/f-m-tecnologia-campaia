import { Card } from "@/components/Card";
import { LoadingState } from "@/components/LoadingState";
import { PageContainer } from "@/components/PageContainer";

export default function CampaignsLoading() {
  return (
    <PageContainer>
      <Card>
        <LoadingState label="Carregando campanhas…" />
      </Card>
    </PageContainer>
  );
}
