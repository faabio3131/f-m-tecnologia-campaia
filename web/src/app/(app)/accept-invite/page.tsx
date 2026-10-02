"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "../../../components/Button";
import { GoogleIdentityButton } from "../../../components/GoogleIdentityButton";
import { Card } from "../../../components/Card";
import { ErrorState } from "../../../components/ErrorState";
import { PageContainer } from "../../../components/PageContainer";
import { PageHeader } from "../../../components/PageHeader";
import { Spinner } from "../../../components/Spinner";
import { ApiClientError } from "../../../lib/api/client";
import { isGoogleIdentityConfigured } from "../../../lib/auth/google-identity-client";
import {
  TEST_IDENTITY_OPTIONS,
  isTestIdentityModeEnabled,
} from "../../../lib/auth/test-identity-client";
import { useAuth } from "../../../providers/AuthProvider";

export default function AcceptInvitePage() {
  return (
    <Suspense
      fallback={
        <PageContainer>
          <Spinner label="Carregando convite" />
        </PageContainer>
      }
    >
      <AcceptInviteForm />
    </Suspense>
  );
}

function AcceptInviteForm() {
  const params = useSearchParams();
  const router = useRouter();
  const { acceptInvitation } = useAuth();
  const token = params.get("token");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const testMode = isTestIdentityModeEnabled();
  const googleIdentityConfigured = isGoogleIdentityConfigured();

  async function acceptWith(idToken: string) {
    if (!token) return;
    setPending(true);
    setError(null);
    try {
      await acceptInvitation(idToken, token, "accept-" + crypto.randomUUID());
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Falha ao aceitar convite.");
    } finally {
      setPending(false);
    }
  }

  return (
    <PageContainer>
      <PageHeader
        title="Aceitar convite"
        description="O convite só cria acesso quando a identidade verificada corresponde ao e-mail convidado."
      />
      <Card>
        {!token ? (
          <ErrorState title="Convite inválido" description="Token de convite ausente." />
        ) : error ? (
          <ErrorState title="Não foi possível aceitar" description={error} />
        ) : null}

        {token && testMode ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <p>Modo de teste: selecione a identidade que aceitará o convite.</p>
            {TEST_IDENTITY_OPTIONS.map((option) => (
              <Button
                key={option.id}
                disabled={pending}
                onClick={() => acceptWith(option.id)}
                data-testid={"accept-invite-identity-" + option.id}
              >
                {option.label}
              </Button>
            ))}
          </div>
        ) : token && googleIdentityConfigured ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <p>Confirme sua Conta Google para aceitar o convite.</p>
            <GoogleIdentityButton
              disabled={pending}
              onIdToken={acceptWith}
              onError={setError}
              text="continue_with"
            />
          </div>
        ) : token ? (
          <ErrorState
            title="Identidade Google não configurada"
            description="A configuração pública do Google Identity Platform ainda não está disponível neste ambiente. O aceite permanece fail-closed."
          />
        ) : null}
      </Card>
    </PageContainer>
  );
}
