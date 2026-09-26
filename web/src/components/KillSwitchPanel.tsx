"use client";

import { useState } from "react";
import { ApiClientError, api } from "../lib/api/client";
import { Button } from "./Button";
import { Card } from "./Card";
import { Input } from "./Input";
import styles from "./KillSwitchPanel.module.css";

/**
 * WP-08 (26/09/2026, reconciliação PR#6): kill switch (parada de emergência).
 *
 * Reconstruído sobre a arquitetura Web da PR #5, não copiado da PR #6 -- ver
 * docs/evidence/RECONCILIACAO_TAKEOVER_FINAL_20260926.md. `POST /kill-switch`
 * (`routes_campaigns.py::kill_switch`) já existia antes deste bloco; este componente só
 * constrói a camada Web sobre ele.
 *
 * Diferente de Budget/Autonomia: kill switch NÃO passa pela fila de aprovação nem exige
 * step-up -- decisão de domínio deliberada e documentada em
 * `campaia_core/permissions.py::REQUIRES_STEP_UP` ("emergência não espera
 * reautenticação; exigir step-up para parar um gasto seria proteger a coisa errada").
 * Só reduz efeito (pausa), nunca amplia -- por isso pode agir de imediato.
 *
 * Escopo desta reconciliação: só os escopos `CAMPAIGN` (esta campanha) e `TENANT` (todas
 * as campanhas deste tenant) foram portados para a Web. `ACCOUNT`/`PLATFORM` mapeiam
 * para conceitos que ainda não têm um seletor natural na UI atual (uma "conta"/"canal"
 * não é algo que o usuário escolhe em nenhuma tela hoje -- simplificação já documentada
 * no próprio backend, achado 13) e `GLOBAL` cruza TODOS os tenants da plataforma sem
 * nenhuma permissão adicional de "administrador de plataforma" no modelo de autorização
 * atual (qualquer OWNER/ADMIN/FINANCE/APPROVER de QUALQUER tenant pode acioná-lo) --
 * expor isso numa tela de um tenant comum seria uma decisão de produto/segurança nova,
 * não portar um comportamento existente. Registrado como pendência para decisão humana,
 * não implementado aqui.
 */

interface KillSwitchResult {
  scope?: string;
  affected_campaign_ids?: string[];
}

export interface KillSwitchPanelProps {
  scope: "CAMPAIGN" | "TENANT";
  /** Obrigatório quando `scope === "CAMPAIGN"` (o `target_id` do contrato). */
  targetId?: string;
  title: string;
  description: string;
  confirmLabel: string;
  onTriggered?: () => void | Promise<void>;
}

export function KillSwitchPanel({
  scope,
  targetId,
  title,
  description,
  confirmLabel,
  onTriggered,
}: KillSwitchPanelProps) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<KillSwitchResult | null>(null);

  async function handleTrigger() {
    setError(null);
    setResult(null);
    setBusy(true);
    try {
      const response = await api.post<KillSwitchResult>(
        "/kill-switch",
        {
          scope,
          target_id: targetId ?? null,
          // Contrato declara `reason` obrigatorio (backend aceita vazio, mas seguimos o
          // contrato aqui) -- sempre um texto real, nunca inventado por conta propria.
          reason: reason.trim() || "Parada de emergência solicitada pela Web (sem motivo informado).",
        },
        { idempotencyKey: `kill-switch-${scope}-${targetId ?? "tenant"}-${crypto.randomUUID()}` },
      );
      setResult(response);
      setReason("");
      await onTriggered?.();
    } catch (err) {
      if (err instanceof ApiClientError && err.code === "INVALID_STATE") {
        setError(
          "Esta campanha não está em um estado que possa ser pausado agora (ex.: ainda em rascunho, nunca publicada).",
        );
      } else {
        setError(
          err instanceof ApiClientError ? err.message : "Falha ao acionar a parada de emergência.",
        );
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className={styles.sectionTitle}>{title}</h2>
      <p className={styles.muted}>{description}</p>

      {error ? <p className={styles.error}>{error}</p> : null}

      {result ? (
        <p className={styles.result} data-testid={`kill-switch-result-${scope.toLowerCase()}`}>
          Acionado — {(result.affected_campaign_ids ?? []).length} campanha(s) afetada(s).
        </p>
      ) : null}

      <div className={styles.form}>
        <Input
          label="Motivo (opcional)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          disabled={busy}
        />
        <Button variant="secondary" disabled={busy} onClick={handleTrigger}>
          {confirmLabel}
        </Button>
      </div>
    </Card>
  );
}
