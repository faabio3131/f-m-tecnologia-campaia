"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Badge } from "../../../../components/Badge";
import { Button } from "../../../../components/Button";
import { Card } from "../../../../components/Card";
import { EmptyState } from "../../../../components/EmptyState";
import { ErrorState } from "../../../../components/ErrorState";
import { Input } from "../../../../components/Input";
import { PageContainer } from "../../../../components/PageContainer";
import { PageHeader } from "../../../../components/PageHeader";
import { Spinner } from "../../../../components/Spinner";
import type { AuditEvent } from "../../../../contracts/types";
import { ApiClientError, api } from "../../../../lib/api/client";
import styles from "./page.module.css";

/**
 * WP-10 (26/09/2026, reconciliação PR#6): trilha de auditoria (`GET /audit-events`).
 * Reconstruído sobre a arquitetura Web da PR #5, não copiado da PR #6 -- ver
 * docs/evidence/RECONCILIACAO_TAKEOVER_FINAL_20260926.md. A rota de backend já existia
 * antes deste bloco (usada por vários WPs anteriores para auditar suas próprias ações);
 * este bloco só constrói a primeira UI para lê-la.
 *
 * Filtro por `campaign_id`: o único filtro que o contrato real oferece
 * (`routes_audit.py::list_audit_events`) -- nenhum outro filtro é inventado aqui.
 * `next_cursor` é sempre `null` no backend real (achado 3/15, documentado no próprio
 * backend: "sem fabricar paginação que não existe") -- por isso esta tela não mostra
 * nenhum controle de paginação (não fabrica o que o backend honestamente não tem).
 * A ordem de exibição (mais recente primeiro) é só uma transformação de exibição no
 * cliente -- o backend real devolve em ordem cronológica ascendente.
 */

const ACTOR_KIND_LABEL: Record<string, string> = {
  USER: "Usuário",
  SYSTEM: "Sistema",
  AI: "IA",
  EXTERNAL_PROVIDER: "Provedor externo",
};

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [campaignIdFilter, setCampaignIdFilter] = useState("");
  const [appliedFilter, setAppliedFilter] = useState<string | null>(null);

  async function load(campaignId: string | null) {
    setLoadError(null);
    try {
      const query = campaignId ? `?campaign_id=${encodeURIComponent(campaignId)}` : "";
      const result = await api.get<{ items: AuditEvent[]; next_cursor: string | null }>(
        `/audit-events${query}`,
      );
      setEvents(result.items);
    } catch (err) {
      setLoadError(
        err instanceof ApiClientError ? err.message : "Falha ao carregar a trilha de auditoria.",
      );
    }
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const result = await api.get<{ items: AuditEvent[]; next_cursor: string | null }>(
          "/audit-events",
        );
        if (active) setEvents(result.items);
      } catch (err) {
        if (active) {
          setLoadError(
            err instanceof ApiClientError
              ? err.message
              : "Falha ao carregar a trilha de auditoria.",
          );
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  async function handleFilterSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = campaignIdFilter.trim() || null;
    setAppliedFilter(trimmed);
    setEvents(null);
    await load(trimmed);
  }

  async function handleClearFilter() {
    setCampaignIdFilter("");
    setAppliedFilter(null);
    setEvents(null);
    await load(null);
  }

  const sortedDescending = events
    ? [...events].sort((a, b) => (b.occurred_at ?? "").localeCompare(a.occurred_at ?? ""))
    : null;

  return (
    <PageContainer>
      <PageHeader
        title="Auditoria"
        description="Trilha real de eventos deste tenant (GET /audit-events). Sem paginação real ainda -- o backend sempre devolve a lista completa de uma vez, não fabricamos controles de próxima página aqui."
      />

      <Card>
        <h2 className={styles.sectionTitle}>Filtrar por campanha</h2>
        <form className={styles.filterBar} onSubmit={handleFilterSubmit}>
          <Input
            label="ID da campanha"
            value={campaignIdFilter}
            onChange={(e) => setCampaignIdFilter(e.target.value)}
          />
          <Button type="submit">Filtrar</Button>
          {appliedFilter ? (
            <Button type="button" variant="secondary" onClick={handleClearFilter}>
              Limpar filtro
            </Button>
          ) : null}
        </form>

        {loadError ? <ErrorState title="Não foi possível carregar" description={loadError} /> : null}

        {events === null && !loadError ? <Spinner label="Carregando trilha de auditoria" /> : null}

        {sortedDescending !== null ? (
          sortedDescending.length === 0 ? (
            <EmptyState
              title={
                appliedFilter
                  ? "Nenhum evento para esta campanha"
                  : "Nenhum evento de auditoria ainda"
              }
            />
          ) : (
            <ul className={styles.list}>
              {sortedDescending.map((event) => (
                <li key={event.id} className={styles.item}>
                  <div className={styles.itemHeader}>
                    <span className={styles.action}>{event.action}</span>
                    <Badge>{ACTOR_KIND_LABEL[event.actor_kind ?? ""] ?? event.actor_kind}</Badge>
                  </div>
                  <p className={styles.itemDetail}>
                    {event.occurred_at ? new Date(event.occurred_at).toLocaleString("pt-BR") : "—"}
                    {" · "}
                    Ator: {event.actor_id ?? "—"}
                    {" · "}
                    Alvo: {event.target}
                  </p>
                  {event.policy_decision_id ? (
                    <p className={styles.itemDetail}>
                      Decisão de política: {event.policy_decision_id}
                    </p>
                  ) : null}
                  {event.evidence && Object.keys(event.evidence).length > 0 ? (
                    <pre className={styles.evidence}>{JSON.stringify(event.evidence, null, 2)}</pre>
                  ) : null}
                </li>
              ))}
            </ul>
          )
        ) : null}
      </Card>
    </PageContainer>
  );
}
