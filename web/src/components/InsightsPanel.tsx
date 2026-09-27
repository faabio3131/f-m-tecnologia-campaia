"use client";

import { useEffect, useState } from "react";
import type { InsightSeries } from "../contracts/types";
import { ApiClientError, api } from "../lib/api/client";
import { Card } from "./Card";
import { ErrorState } from "./ErrorState";
import { Spinner } from "./Spinner";
import styles from "./InsightsPanel.module.css";

/**
 * WP-11 (26/09/2026, reconciliação PR#6): métricas da campanha (`GET
 * /campaigns/{campaignId}/insights`). Reconstruído sobre a arquitetura Web da PR #5,
 * não copiado da PR #6 -- ver docs/evidence/RECONCILIACAO_TAKEOVER_FINAL_20260926.md.
 * A rota de backend já existia antes deste bloco (placeholder honesto: "No analytics
 * layer implemented yet in campaia_core; this is an honest placeholder, not
 * fabricated data.") -- este componente só constrói a camada Web sobre ela.
 *
 * Disciplina de honestidade do próprio backend replicada aqui: quando `points` vem
 * vazio, a Web mostra o `note` real devolvido pelo backend em vez de inventar um
 * gráfico, um placeholder genérico ou qualquer número. Quando `points` tiver dados
 * reais no futuro (camada de analytics ainda não existe), a Web já sabe listá-los.
 */
export interface InsightsPanelProps {
  campaignId: string;
}

export function InsightsPanel({ campaignId }: InsightsPanelProps) {
  const [insights, setInsights] = useState<InsightSeries | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setBusy(true);
      setError(null);
      try {
        const result = await api.get<InsightSeries>(`/campaigns/${campaignId}/insights`);
        if (!cancelled) setInsights(result);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiClientError ? err.message : "Falha ao carregar as métricas.");
        }
      } finally {
        if (!cancelled) setBusy(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [campaignId]);

  return (
    <Card>
      <h2 className={styles.sectionTitle}>Métricas</h2>
      {busy ? <Spinner /> : null}
      {error ? (
        <ErrorState
          title="Não foi possível carregar as métricas"
          description={error}
        />
      ) : null}
      {!busy && !error && insights ? (
        insights.points && insights.points.length > 0 ? (
          <ul className={styles.list}>
            {insights.points.map((point, index) => (
              <li key={index} className={styles.item}>
                {point.date} · {point.channel}: {point.impressions} impressões,{" "}
                {point.clicks} cliques, {point.conversions} conversões
                {point.cpa !== null && point.cpa !== undefined ? ` · CPA ${point.cpa}` : ""}
              </li>
            ))}
          </ul>
        ) : (
          // `note` é sempre devolvido pelo backend real (confirmado por execução direta
          // nesta sessão, achado 15) -- mostrado literalmente, nunca substituído por um
          // texto genérico da Web, para não esconder a limitação real do backend.
          <p className={styles.muted}>{insights.note}</p>
        )
      ) : null}
    </Card>
  );
}
