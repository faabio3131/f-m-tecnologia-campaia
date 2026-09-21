import { Card } from "@/components/Card";
import { LoadingState } from "@/components/LoadingState";
import { PageContainer } from "@/components/PageContainer";

/**
 * WP-03: Next.js App Router's own Suspense-boundary convention -- rendered automatically
 * while the async Server Component in ./page.tsx is awaiting getServerSession /
 * getServerSessionMemberships, so a slow BFF response never leaves a blank screen.
 */
export default function DashboardLoading() {
  return (
    <PageContainer>
      <Card>
        <LoadingState label="Carregando sessão…" />
      </Card>
    </PageContainer>
  );
}
