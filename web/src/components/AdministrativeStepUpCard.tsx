"use client";

import { Card } from "./Card";
import { GoogleIdentityButton } from "./GoogleIdentityButton";
import { isGoogleIdentityConfigured } from "../lib/auth/google-identity-client";
import styles from "./AdministrativeStepUpCard.module.css";

export interface AdministrativeStepUpCardProps {
  ready: boolean;
  testMode: boolean;
  message?: string | null;
  onIdToken: (idToken: string) => Promise<void> | void;
  onError?: (message: string) => void;
}

export function AdministrativeStepUpCard({
  ready,
  testMode,
  message,
  onIdToken,
  onError,
}: AdministrativeStepUpCardProps) {
  if (testMode) return null;

  const configured = isGoogleIdentityConfigured();

  return (
    <Card>
      <h2 className={styles.title}>Reautenticação administrativa</h2>
      <p className={styles.description}>
        Alterações de usuários, papéis e unidades exigem uma autenticação Google recente.
        A elevação fica vinculada somente à sessão atual.
      </p>
      {configured ? (
        <>
          <GoogleIdentityButton
            text="continue_with"
            onIdToken={onIdToken}
            onError={onError}
          />
          <p className={styles.status} data-testid="administrative-step-up-status">
            {ready
              ? "Identidade revalidada. A próxima operação sensível pode continuar."
              : message ?? "Reautentique antes de uma operação sensível."}
          </p>
        </>
      ) : (
        <p className={styles.status}>
          Configuração externa do Google Identity Platform ainda não está provisionada
          neste ambiente. As operações sensíveis permanecem bloqueadas por segurança.
        </p>
      )}
    </Card>
  );
}
