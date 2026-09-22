import { ApprovalDecisionCard } from "@/components/ApprovalDecisionCard";
import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { ErrorState } from "@/components/ErrorState";
import { PageContainer } from "@/components/PageContainer";
import { getPublicBffOrigin, getServerApprovals, getServerSession } from "@/lib/session";
import styles from "./page.module.css";

/**
 * WP-05: fila de aprovação, fecha a jornada crítica (briefing -> estratégia -> validação ->
 * aprovação). Lista TODAS as aprovações do tenant (GET /approvals, sem filtro de
 * campanha/status no contrato) -- decisão (aprovar/rejeitar/pedir ajustes) só é oferecida
 * para as PENDING; segregação de funções é sempre validada pelo servidor, nunca pela UI (ver
 * ApprovalDecisionCard.tsx).
 */
export default async function ApprovalsPage() {
  const bffOrigin = getPublicBffOrigin();

  if (!bffOrigin) {
    return (
      <PageContainer>
        <Card>
          <ErrorState
            title="Não configurado"
            description="A variável de ambiente NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN não está definida — a fila de aprovação não sabe onde está o backend (BFF)."
          />
        </Card>
      </PageContainer>
    );
  }

  const me = await getServerSession();
  if (!me) {
    const loginUrl = `${bffOrigin}/auth/login?redirect_after_login=${encodeURIComponent("/approvals")}`;
    return (
      <PageContainer>
        <header className={styles.header}>
          <Badge tone="neutral">CampaIA Web — Aprovações (WP-05)</Badge>
          <h1 className={styles.title}>Você não está autenticado</h1>
        </header>
        <Card>
          <a className={styles.loginLink} href={loginUrl}>
            Entrar
          </a>
        </Card>
      </PageContainer>
    );
  }

  const approvals = await getServerApprovals();
  if (approvals === null) {
    return (
      <PageContainer>
        <Card>
          <ErrorState
            title="Não foi possível carregar as aprovações"
            description="GET /approvals falhou apesar de uma sessão válida existir. Tente recarregar a página."
          />
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <header className={styles.header}>
        <Badge tone="accent">CampaIA Web — Aprovações (WP-05)</Badge>
        <h1 className={styles.title}>Fila de aprovação</h1>
      </header>

      <Card>
        {approvals.length === 0 ? (
          <p className={styles.emptyNote}>Nenhuma aprovação pendente ou registrada ainda.</p>
        ) : (
          <div className={styles.list}>
            {approvals.map((approval) => (
              <ApprovalDecisionCard key={approval.id} bffOrigin={bffOrigin} approval={approval} />
            ))}
          </div>
        )}
      </Card>
    </PageContainer>
  );
}
