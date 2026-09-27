"use client";

import { useEffect, useState } from "react";
import type { ApprovalRequest, AutonomySettings } from "../contracts/types";
import { ApiClientError, api } from "../lib/api/client";
import { Button } from "./Button";
import { Card } from "./Card";
import { Input } from "./Input";
import styles from "./AutonomyPanel.module.css";

const STEP_UP_HEADER = { "x-step-up-token": "web-ui-confirmacao-explicita" };

/**
 * WP-07 (26/09/2026, reconciliação PR#6): nível de autonomia.
 *
 * Reconstruído sobre a arquitetura Web da PR #5 (Etapa 2), não copiado da PR #6 -- ver
 * docs/evidence/RECONCILIACAO_TAKEOVER_FINAL_20260926.md. As duas rotas de backend
 * usadas aqui (`GET`/`PUT /autonomy`) já existiam antes deste bloco; este componente só
 * constrói a camada Web sobre elas.
 *
 * Autonomia é uma configuração de TENANT, não de campanha -- por isso vive em
 * `/settings`, não em `campaigns/[campaignId]`. Mas `POST /approvals` (rota já existente,
 * reaproveitada, ver `routes_approvals.py::create_approval`) exige um `campaign_id` real
 * mesmo para uma aprovação `AUTONOMY_CHANGE` -- restrição já presente no CURRENT (mesmo
 * padrão usado pelos testes de backend em `test_smoke_endpoints.py::test_autonomy_get_and_put`),
 * não inventada aqui. Por isso este painel precisa de uma campanha "âncora" do tenant; se
 * não existir nenhuma campanha ainda, a proposta fica honestamente desabilitada (ver
 * `anchorCampaignId`), em vez de fabricar uma campanha ou meio de contorno.
 *
 * Achado real de contrato desta reconciliação: `GET /autonomy` sempre devolve
 * `max_level_allowed` (confirmado por execução real de
 * `AutonomyResponse.model_dump_json()`), mas o contrato nunca declarava esse campo --
 * corrigido de forma aditiva em `contracts/bff-openapi.yaml`, mesma classe do achado do
 * WP-06 (Decimal/budget).
 *
 * Limitação real do CURRENT, não corrigida aqui (fora do escopo de portar a Web): a
 * aprovação `AUTONOMY_CHANGE` não carrega o nível pretendido -- `PUT /autonomy` só exige
 * `approval_id` com status `APPROVED`, o nível efetivo é escolhido por quem aplica, não
 * o mesmo que o aprovador reviu. Documentado honestamente como achado, não escondido nem
 * "corrigido" por conta própria nesta sessão (mudaria contrato/domínio, não só a Web).
 */

function levelBadge(label: string): string {
  return label;
}

export interface AutonomyPanelProps {
  /** Primeira campanha real do tenant, se existir -- usada como âncora da aprovação. */
  anchorCampaignId: string | null;
}

export function AutonomyPanel({ anchorCampaignId }: AutonomyPanelProps) {
  const [settings, setSettings] = useState<AutonomySettings | null>(null);
  const [pendingApproval, setPendingApproval] = useState<ApprovalRequest | null>(null);
  const [proposedLevel, setProposedLevel] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function pickRelevant(all: ApprovalRequest[]): ApprovalRequest | null {
    const relevant = all
      .filter((a) => a.kind === "AUTONOMY_CHANGE")
      .filter((a) => a.status === "PENDING" || a.status === "APPROVED")
      .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
    return relevant[0] ?? null;
  }

  async function reload() {
    try {
      const [autonomy, approvals] = await Promise.all([
        api.get<AutonomySettings>("/autonomy"),
        api.get<ApprovalRequest[]>("/approvals"),
      ]);
      setSettings(autonomy);
      setPendingApproval(pickRelevant(approvals));
    } catch (err) {
      setLoadError(
        err instanceof ApiClientError ? err.message : "Falha ao carregar o nível de autonomia.",
      );
    }
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [autonomy, approvals] = await Promise.all([
          api.get<AutonomySettings>("/autonomy"),
          api.get<ApprovalRequest[]>("/approvals"),
        ]);
        if (active) {
          setSettings(autonomy);
          setPendingApproval(pickRelevant(approvals));
        }
      } catch (err) {
        if (active) {
          setLoadError(
            err instanceof ApiClientError
              ? err.message
              : "Falha ao carregar o nível de autonomia.",
          );
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  async function handlePropose() {
    setActionError(null);
    if (anchorCampaignId === null) {
      setActionError(
        "É necessário existir ao menos uma campanha no tenant para propor uma mudança de nível de autonomia.",
      );
      return;
    }
    const level = Number(proposedLevel);
    if (!Number.isInteger(level) || level < 0 || level > 3) {
      setActionError("Informe um nível de autonomia válido (0 a 3).");
      return;
    }
    setBusy(true);
    try {
      const result = await api.post<ApprovalRequest>(
        "/approvals",
        {
          campaign_id: anchorCampaignId,
          kind: "AUTONOMY_CHANGE",
          // Informativo apenas -- PUT /autonomy nao le este valor, ver nota de limitacao
          // acima. Ainda assim registrado para dar contexto a quem decidir.
          amount: proposedLevel,
        },
        { idempotencyKey: `autonomy-propose-${crypto.randomUUID()}` },
      );
      setPendingApproval(result);
      setProposedLevel("");
    } catch (err) {
      setActionError(
        err instanceof ApiClientError ? err.message : "Falha ao propor a mudança de nível.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleApply() {
    if (!pendingApproval || pendingApproval.amount === undefined || pendingApproval.amount === null) {
      return;
    }
    setActionError(null);
    setBusy(true);
    try {
      await api.put(
        "/autonomy",
        { level: Number(pendingApproval.amount), approval_id: pendingApproval.id },
        {
          headers: STEP_UP_HEADER,
          idempotencyKey: `autonomy-apply-${pendingApproval.id}`,
        },
      );
      await reload();
    } catch (err) {
      setActionError(
        err instanceof ApiClientError ? err.message : "Falha ao aplicar a mudança de nível.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className={styles.sectionTitle}>Nível de autonomia</h2>

      {loadError ? <p className={styles.error}>{loadError}</p> : null}

      {settings ? (
        <dl className={styles.summary}>
          <div>
            <dt>Nível atual</dt>
            <dd data-testid="autonomy-level-label">{levelBadge(settings.level_label ?? "—")}</dd>
          </div>
          <div>
            <dt>Teto permitido para este tenant</dt>
            <dd>{settings.max_level_allowed ?? "—"}</dd>
          </div>
          <div>
            <dt>Variação máxima de orçamento por nível</dt>
            <dd>{settings.max_budget_change_pct ?? "—"}%</dd>
          </div>
        </dl>
      ) : loadError ? null : (
        <p className={styles.muted}>Carregando…</p>
      )}

      {settings?.always_require_human && settings.always_require_human.length > 0 ? (
        <p className={styles.muted}>
          Sempre exige decisão humana, em qualquer nível: {settings.always_require_human.join(", ")}.
        </p>
      ) : null}

      {actionError ? <p className={styles.error}>{actionError}</p> : null}

      {pendingApproval ? (
        pendingApproval.status === "APPROVED" ? (
          <div className={styles.pendingBox}>
            <p>Mudança de nível aprovada — pronta para aplicar.</p>
            <Button disabled={busy} onClick={handleApply}>
              Aplicar nível de autonomia
            </Button>
          </div>
        ) : (
          <p className={styles.muted}>
            Pedido de mudança de nível pendente — decida na fila de{" "}
            <a href="/approvals">Aprovações</a>.
          </p>
        )
      ) : (
        <div className={styles.proposeBox}>
          <Input
            label="Novo nível (0 a 3)"
            type="number"
            min="0"
            max="3"
            step="1"
            value={proposedLevel}
            onChange={(e) => setProposedLevel(e.target.value)}
            disabled={busy || anchorCampaignId === null}
          />
          <Button disabled={busy || anchorCampaignId === null} onClick={handlePropose}>
            Propor mudança de nível
          </Button>
          {anchorCampaignId === null ? (
            <p className={styles.muted}>
              É necessário existir ao menos uma campanha no tenant para propor uma mudança
              de nível de autonomia (restrição do backend real, não desta tela).
            </p>
          ) : null}
        </div>
      )}
    </Card>
  );
}
