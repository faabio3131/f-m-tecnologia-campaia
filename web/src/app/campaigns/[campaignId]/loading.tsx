import { Card } from "@/components/Card";
import { LoadingState } from "@/components/LoadingState";
import { PageContainer } from "@/components/PageContainer";

export default function CampaignDetailLoading() {
  return (
    <PageContainer>
      <Card>
        <LoadingState label="Carregando campanha…" />
      </Card>
    </PageContainer>
  );
}
