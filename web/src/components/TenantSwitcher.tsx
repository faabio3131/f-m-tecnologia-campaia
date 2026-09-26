"use client";

import { useEffect, useState } from "react";
import { ApiClientError, api } from "../lib/api/client";
import type { MembershipsResponse } from "../types/session";
import { useAuth } from "../providers/AuthProvider";
import { Button } from "./Button";
import { ErrorState } from "./ErrorState";
import { Spinner } from "./Spinner";
import styles from "./TenantSwitcher.module.css";

/**
 * Lista os vinculos reais da sessao (`GET /me/memberships`, WP-03) e troca o vinculo
 * ativo (`AuthProvider.switchMembership`, que chama `POST /auth/session/switch`).
 * Autoridade de qual vinculo e' valido continua 100% no backend -- este componente so
 * lista o que o backend ja confirmou pertencer a esta identidade e repassa a escolha.
 */
export function TenantSwitcher() {
  const { session, switchMembership } = useAuth();
  const [memberships, setMemberships] = useState<MembershipsResponse["memberships"] | null>(
    null,
  );
  const [loadError, setLoadError] = useState<string | null>(null);
  const [switchingTo, setSwitchingTo] = useState<string | null>(null);
  const [switchError, setSwitchError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const result = await api.get<MembershipsResponse>("/me/memberships");
        if (active) setMemberships(result.memberships);
      } catch (err) {
        if (!active) return;
        setLoadError(
          err instanceof ApiClientError ? err.message : "Falha ao carregar vínculos.",
        );
      }
    })();
    return () => {
      active = false;
    };
    // Refaz a listagem sempre que a sessão ativa muda (após uma troca bem-sucedida, por
    // exemplo), para refletir qual vínculo está marcado como ativo agora.
  }, [session?.tenant_id, session?.business_unit_id]);

  if (loadError) {
    return (
      <ErrorState
        title="Não foi possível carregar os vínculos"
        description={loadError}
      />
    );
  }

  if (memberships === null) {
    return <Spinner label="Carregando vínculos" />;
  }

  if (memberships.length <= 1) {
    return (
      <p className={styles.singleMembership}>
        Esta conta tem vínculo com apenas um tenant/unidade — nada para trocar.
      </p>
    );
  }

  async function handleSwitch(targetUserId: string) {
    setSwitchError(null);
    setSwitchingTo(targetUserId);
    try {
      await switchMembership(targetUserId);
    } catch (err) {
      setSwitchError(
        err instanceof ApiClientError ? err.message : "Falha ao trocar de tenant/unidade.",
      );
    } finally {
      setSwitchingTo(null);
    }
  }

  return (
    <div className={styles.list}>
      {switchError ? (
        <ErrorState title="Não foi possível trocar" description={switchError} />
      ) : null}
      {memberships.map((membership) => (
        <div key={membership.user_id} className={styles.row}>
          <div>
            <p className={styles.tenant}>{membership.tenant_id}</p>
            <p className={styles.detail}>
              {membership.business_unit_id ?? "todas as unidades"} ·{" "}
              {membership.roles.join(", ")}
            </p>
          </div>
          {membership.active ? (
            <span className={styles.activeBadge}>Ativo</span>
          ) : (
            <Button
              variant="secondary"
              disabled={switchingTo !== null}
              onClick={() => handleSwitch(membership.user_id)}
              data-testid={`switch-membership-${membership.user_id}`}
            >
              {switchingTo === membership.user_id ? "Trocando…" : "Trocar para este"}
            </Button>
          )}
        </div>
      ))}
    </div>
  );
}
