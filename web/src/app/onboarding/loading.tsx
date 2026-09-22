import { Card } from "@/components/Card";
import { LoadingState } from "@/components/LoadingState";
import { PageContainer } from "@/components/PageContainer";

export default function OnboardingLoading() {
  return (
    <PageContainer>
      <Card>
        <LoadingState label="Carregando onboarding…" />
      </Card>
    </PageContainer>
  );
}
