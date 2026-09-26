"use client";

import { useState } from "react";
import type { Capability } from "../contracts/types";
import { ApiClientError, api } from "../lib/api/client";
import { Badge } from "./Badge";
import { Button } from "./Button";
import styles from "./CapabilitiesPanel.module.css";

/**
 * WP-09 (26/09/2026, reconciliação PR#6): capacidades da conexão (`GET
 * /connections/{connectionId}/capabilities`). Reconstruído sobre a arquitetura Web da
 * PR #5, não copiado da PR #6 -- ver
 * docs/evidence/RECONCILIACAO_TAKEOVER_FINAL_20260926.md. A rota de backend já existia
 * antes deste bloco; este componente só constrói a camada Web sobre ela.
 *
 * "Fonte da verdade para a interface. O app só oferece ação com `supported = true`"
 * (contrato) -- este painel é só leitura/exibição por enquanto (nenhuma ação de
 * publicação real existe ainda na Web, ver nota em campaigns/[campaignId]/page.tsx),
 * mas já mostra `supported`/`requires_approval` com a mesma disciplina: nunca inventa
 * `evidence_url` quando o backend devolve `null` (achado 7, documentado no próprio
 * backend -- não há ainda rastreamento real de evidência), mostra "sem evidência
 * registrada" em vez de esconder o campo ou fabricar um link.
 */
export interface CapabilitiesPanelProps {
  connectionId: string;
}

export function CapabilitiesPanel({ connectionId }: CapabilitiesPanelProps) {
  const [capabilities, setCapabilities] = useState<Capability[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState(false);

  async function handleToggle() {
    if (expanded) {
      setExpanded(false);
      return;
    }
    setExpanded(true);
    if (capabilities !== null) return;
    setError(null);
    setBusy(true);
    try {
      const result = await api.get<Capability[]>(`/connections/${connectionId}/capabilities`);
      setCapabilities(result);
    } catch (err) {
      setError(
        err instanceof ApiClientError ? err.message : "Falha ao carregar as capacidades.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.wrapper}>
      <Button
        variant="secondary"
        disabled={busy}
        onClick={handleToggle}
        data-testid={`toggle-capabilities-${connectionId}`}
      >
        {expanded ? "Ocultar capacidades" : "Ver capacidades"}
      </Button>

      {expanded ? (
        <div className={styles.panel}>
          {error ? <p className={styles.error}>{error}</p> : null}
          {busy ? <p className={styles.muted}>Carregando…</p> : null}
          {capabilities ? (
            capabilities.length === 0 ? (
              <p className={styles.muted}>Nenhuma capacidade registrada para esta conexão.</p>
            ) : (
              <ul className={styles.list}>
                {capabilities.map((cap) => (
                  <li key={`${cap.capability_key}-${cap.country}-${cap.api_version}`} className={styles.item}>
                    <div className={styles.itemHeader}>
                      <span className={styles.capabilityKey}>{cap.capability_key}</span>
                      <Badge tone={cap.supported ? "accent" : "warning"}>
                        {cap.supported ? "Suportada" : "Não suportada"}
                      </Badge>
                    </div>
                    <p className={styles.itemDetail}>
                      País: {cap.country} · Versão de API: {cap.api_version}
                      {cap.requires_approval ? " · exige aprovação" : ""}
                    </p>
                    <p className={styles.itemDetail}>
                      Verificado em:{" "}
                      {cap.verified_at ? new Date(cap.verified_at).toLocaleString("pt-BR") : "—"}
                    </p>
                    <p className={styles.itemDetail}>
                      Evidência:{" "}
                      {cap.evidence_url ? (
                        <a href={cap.evidence_url} target="_blank" rel="noreferrer">
                          {cap.evidence_url}
                        </a>
                      ) : (
                        "sem evidência registrada"
                      )}
                    </p>
                    {cap.notes ? <p className={styles.itemDetail}>{cap.notes}</p> : null}
                  </li>
                ))}
              </ul>
            )
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
