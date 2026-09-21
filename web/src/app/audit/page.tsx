import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { ErrorState } from "@/components/ErrorState";
import { PageContainer } from "@/components/PageContainer";
import { getPublicBffOrigin, getServerAuditEvents, getServerSession } from "@/lib/session";
import styles from "./page.module.css";

/**
 * WP-10: trilha de auditoria real do tenant (GET /audit-events), já existente e já escrita
 * por praticamente todo bloco desde o WP-04 (OAUTH_START, CONNECTION_CREATE,
 * CONNECTION_REVOKE, APPROVAL_*, BUDGET_CHANGE, AUTONOMY_CHANGE, KILL_SWITCH) -- mas nenhuma
 * tela jamais exibiu esse histórico até este bloco. Nenhuma rota de backend nova.
 *
 * `AuditEvent.target` é um campo genérico ("o que quer que seja o alvo desta ação", achado 15
 * do próprio backend) -- exibido aqui exatamente como a API devolve, nunca traduzido para um
 * nome legível que a Web não pode confirmar com certeza (para ações de campanha é o
 * campaign_id; para outras, pode ser um connection_id ou o próprio escopo do kill switch).
 *
 * Sem paginação real na API (`next_cursor` sempre null, comentário do próprio
 * routes_audit.py) -- esta tela exibe honestamente a lista completa devolvida, sem fabricar
 * paginação que não existe. A API devolve em ordem cronológica crescente; reordenada aqui
 * (mais recente primeiro) só para exibição -- decisão puramente de apresentação, nunca uma
 * segunda fonte de verdade sobre a ordem real dos eventos.
 */
export default async function AuditPage({
  searchParams,
}: {
  searchParams: Promise<{ campaign_id?: string }>;
}) {
  const { campaign_id: campaignId } = await searchParams;
  const bffOrigin = getPublicBffOrigin();

  if (!bffOrigin) {
    return (
      <PageContainer>
        <Card>
          <ErrorState
            title="Não configurado"
            description="A variável de ambiente NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN não está definida — a trilha de auditoria não sabe onde está o backend (BFF)."
          />
        </Card>
      </PageContainer>
    );
  }

  const me = await getServerSession();
  if (!me) {
    const loginUrl = `${bffOrigin}/auth/login?redirect_after_login=${encodeURIComponent("/audit")}`;
    return (
      <PageContainer>
        <header className={styles.header}>
          <Badge tone="neutral">CampaIA Web — Auditoria (WP-10)</Badge>
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

  const events = await getServerAuditEvents(campaignId);
  if (events === null) {
    return (
      <PageContainer>
        <Card>
          <ErrorState
            title="Não foi possível carregar a trilha de auditoria"
            description="GET /audit-events falhou apesar de uma sessão válida existir — a permissão AUDIT_VIEW pode estar ausente, ou a leitura falhou por outro motivo. Tente recarregar a página."
          />
        </Card>
      </PageContainer>
    );
  }

  // Reordenação apenas de exibição -- ver comentário do módulo.
  const newestFirst = [...events].reverse();

  return (
    <PageContainer>
      <header className={styles.header}>
        <Badge tone="accent">CampaIA Web — Auditoria (WP-10)</Badge>
        <h1 className={styles.title}>Trilha de auditoria</h1>
      </header>

      {campaignId ? (
        <p className={styles.filterNote}>
          Filtrado pela campanha <code>{campaignId}</code> —{" "}
          <a href="/audit">ver todos os eventos</a>.
        </p>
      ) : null}

      <Card>
        {newestFirst.length === 0 ? (
          <p className={styles.emptyNote}>Nenhum evento de auditoria registrado ainda.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Quando</th>
                <th>Quem</th>
                <th>Ação</th>
                <th>Alvo</th>
              </tr>
            </thead>
            <tbody>
              {newestFirst.map((event) => (
                <tr key={event.id}>
                  <td>{event.occurred_at}</td>
                  <td>
                    {event.actor_kind}
                    {event.actor_id ? ` — ${event.actor_id}` : ""}
                  </td>
                  <td>{event.action}</td>
                  <td>{event.target}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </PageContainer>
  );
}
