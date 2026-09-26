"use client";

import { useEffect, useState } from "react";
import { Button } from "../../../../components/Button";
import { Card } from "../../../../components/Card";
import { ErrorState } from "../../../../components/ErrorState";
import { Input } from "../../../../components/Input";
import { PageContainer } from "../../../../components/PageContainer";
import { PageHeader } from "../../../../components/PageHeader";
import { Spinner } from "../../../../components/Spinner";
import type { Connection, Provider } from "../../../../contracts/types";
import { ApiClientError, api } from "../../../../lib/api/client";
import styles from "./page.module.css";

/**
 * WP-04 (26/09/2026): Conexões reais contra `POST /connections/oauth/start` ->
 * `POST /connections/oauth/callback` -> `GET /connections` (achado corrigido nesta
 * sessão: `oauth_start` sozinho nunca criava uma Connection -- ver
 * EVIDENCIA_WP04_ONBOARDING_BRAND_KIT_20260926.md). Ainda simulado: nenhum provider
 * real é contatado, a "seleção de conta" é um formulário que representa o que o
 * usuário escolheria no provedor real.
 *
 * Step-up (X-Step-Up-Token): o backend exige reautenticação recente para
 * CONNECTION_MANAGE. Não existe ainda um desafio real de step-up na Web (depende do
 * item 1.6, Google Identity Platform real) -- por isso a confirmação abaixo é
 * honesta sobre o que é: uma confirmação explícita do usuário, não um desafio de
 * segurança real. Nunca envia o header silenciosamente sem essa confirmação.
 */
const PROVIDERS: { id: Provider; label: string }[] = [
  { id: "GOOGLE_ADS", label: "Google Ads" },
  { id: "META", label: "Meta (Facebook/Instagram)" },
  { id: "WHATSAPP", label: "WhatsApp Business" },
];

const STEP_UP_HEADER = { "x-step-up-token": "web-ui-confirmacao-explicita" };

type FlowState =
  | { stage: "idle" }
  | { stage: "confirming"; provider: Provider }
  | { stage: "selecting-account"; provider: Provider; authorizationUrl: string; state: string };

export default function ConnectionsPage() {
  const [connections, setConnections] = useState<Connection[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [flow, setFlow] = useState<FlowState>({ stage: "idle" });
  const [flowError, setFlowError] = useState<string | null>(null);
  const [externalAccountId, setExternalAccountId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);

  async function loadConnections() {
    try {
      const result = await api.get<Connection[]>("/connections");
      setConnections(result);
    } catch (err) {
      setLoadError(
        err instanceof ApiClientError ? err.message : "Falha ao carregar conexões.",
      );
    }
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const result = await api.get<Connection[]>("/connections");
        if (active) setConnections(result);
      } catch (err) {
        if (active) {
          setLoadError(
            err instanceof ApiClientError ? err.message : "Falha ao carregar conexões.",
          );
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  function connectionFor(provider: Provider): Connection | undefined {
    return connections?.find((c) => c.provider === provider && c.status === "ACTIVE");
  }

  async function handleConfirmStart(provider: Provider) {
    setFlowError(null);
    setBusy(true);
    try {
      const result = await api.post<{ authorization_url: string; state: string }>(
        "/connections/oauth/start",
        { provider },
        { headers: STEP_UP_HEADER },
      );
      setFlow({
        stage: "selecting-account",
        provider,
        authorizationUrl: result.authorization_url,
        state: result.state,
      });
    } catch (err) {
      setFlowError(
        err instanceof ApiClientError ? err.message : "Falha ao iniciar a conexão.",
      );
      setFlow({ stage: "idle" });
    } finally {
      setBusy(false);
    }
  }

  async function handleCompleteCallback() {
    if (flow.stage !== "selecting-account") return;
    setFlowError(null);
    setBusy(true);
    try {
      await api.post(
        "/connections/oauth/callback",
        {
          state: flow.state,
          external_account_id: externalAccountId,
          display_name: displayName,
        },
        {
          headers: STEP_UP_HEADER,
          idempotencyKey: `oauth-callback-${flow.state}`,
        },
      );
      setFlow({ stage: "idle" });
      setExternalAccountId("");
      setDisplayName("");
      await loadConnections();
    } catch (err) {
      setFlowError(
        err instanceof ApiClientError ? err.message : "Falha ao concluir a conexão.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageContainer>
      <PageHeader
        title="Conexões"
        description="Cada canal é opcional individualmente. Nenhum provider real é contatado ainda — fluxo simulado, aguardando integração real (Fase 5–7)."
      />

      {loadError ? <ErrorState title="Não foi possível carregar" description={loadError} /> : null}
      {flowError ? <ErrorState title="Não foi possível continuar" description={flowError} /> : null}

      {connections === null && !loadError ? <Spinner label="Carregando conexões" /> : null}

      {connections !== null ? (
        <div className={styles.grid}>
          {PROVIDERS.map(({ id, label }) => {
            const connection = connectionFor(id);
            return (
              <Card key={id} className={styles.card}>
                <p className={styles.providerName}>{label}</p>
                {connection ? (
                  <p className={styles.status}>
                    Conectado — {connection.display_name}
                  </p>
                ) : (
                  <p className={styles.statusMuted}>Não conectado</p>
                )}

                {!connection && flow.stage === "idle" ? (
                  <Button
                    variant="secondary"
                    disabled={busy}
                    onClick={() => setFlow({ stage: "confirming", provider: id })}
                    data-testid={`connect-${id}`}
                  >
                    Conectar
                  </Button>
                ) : null}

                {flow.stage === "confirming" && flow.provider === id ? (
                  <div className={styles.confirmBox}>
                    <p className={styles.confirmText}>
                      Esta ação exige reautenticação recente. Confirmar para continuar
                      (desafio real de reautenticação pendente do item 1.6).
                    </p>
                    <div className={styles.confirmActions}>
                      <Button disabled={busy} onClick={() => handleConfirmStart(id)}>
                        Confirmar e conectar
                      </Button>
                      <Button
                        variant="secondary"
                        disabled={busy}
                        onClick={() => setFlow({ stage: "idle" })}
                      >
                        Cancelar
                      </Button>
                    </div>
                  </div>
                ) : null}

                {flow.stage === "selecting-account" && flow.provider === id ? (
                  <div className={styles.confirmBox}>
                    <p className={styles.confirmText}>
                      Selecione a conta (simulado — nenhum provedor real foi
                      contatado; URL de autorização: {flow.authorizationUrl}).
                    </p>
                    <Input
                      label="ID da conta"
                      value={externalAccountId}
                      onChange={(e) => setExternalAccountId(e.target.value)}
                    />
                    <Input
                      label="Nome de exibição"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                    />
                    <div className={styles.confirmActions}>
                      <Button
                        disabled={busy || !externalAccountId || !displayName}
                        onClick={handleCompleteCallback}
                        data-testid={`complete-connection-${id}`}
                      >
                        Concluir conexão
                      </Button>
                      <Button
                        variant="secondary"
                        disabled={busy}
                        onClick={() => setFlow({ stage: "idle" })}
                      >
                        Cancelar
                      </Button>
                    </div>
                  </div>
                ) : null}
              </Card>
            );
          })}
        </div>
      ) : null}
    </PageContainer>
  );
}
