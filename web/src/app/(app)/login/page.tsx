"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "../../../components/Button";
import { Card } from "../../../components/Card";
import { ErrorState } from "../../../components/ErrorState";
import { PageContainer } from "../../../components/PageContainer";
import { PageHeader } from "../../../components/PageHeader";
import { Spinner } from "../../../components/Spinner";
import { ApiClientError } from "../../../lib/api/client";
import {
  TEST_IDENTITY_OPTIONS,
  isTestIdentityModeEnabled,
} from "../../../lib/auth/test-identity-client";
import { useAuth } from "../../../providers/AuthProvider";
import styles from "./page.module.css";

function friendlyLoginError(err: unknown): string {
  if (err instanceof ApiClientError) {
    if (err.code === "UNAUTHENTICATED") {
      return "Não foi possível confirmar sua identidade. Tente novamente.";
    }
    if (err.code === "PERMISSION_DENIED") {
      return "Sua conta foi autenticada, mas está sem vínculo com nenhum tenant do CampaIA.";
    }
    return err.message;
  }
  return "Falha inesperada ao tentar entrar. Tente novamente.";
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <PageContainer>
          <Spinner label="Carregando" />
        </PageContainer>
      }
    >
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const { status, login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const testMode = isTestIdentityModeEnabled();

  // Nunca confia em `?next=` como destino de navegacao sem validar --
  // so aceita caminho relativo interno (`/algo`), nunca URL absoluta nem
  // protocol-relative (`//host/...`), para nao virar open redirect apos login.
  const rawNext = searchParams.get("next");
  const nextPath =
    rawNext && rawNext.startsWith("/") && !rawNext.startsWith("//") ? rawNext : "/dashboard";

  useEffect(() => {
    if (status === "authenticated") {
      router.replace(nextPath);
    }
  }, [status, nextPath, router]);

  if (status === "bootstrapping") {
    return (
      <PageContainer>
        <Spinner label="Verificando sessão" />
      </PageContainer>
    );
  }

  async function handleTestSignIn(idToken: string) {
    setPending(true);
    setError(null);
    try {
      await login(idToken);
    } catch (err) {
      setError(friendlyLoginError(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <PageContainer>
      <PageHeader
        title="Entrar no CampaIA"
        description="Autenticação real via Google Identity Platform (ADR-0018/ADR-0022)."
      />
      <Card className={styles.card}>
        {error ? <ErrorState title="Não foi possível entrar" description={error} /> : null}

        {testMode ? (
          <div className={styles.testOptions}>
            <p className={styles.testNotice}>
              Modo de teste ativo (harness de E2E) — nunca disponível em produção.
            </p>
            {TEST_IDENTITY_OPTIONS.map((option) => (
              <Button
                key={option.id}
                onClick={() => handleTestSignIn(option.id)}
                disabled={pending}
                data-testid={`test-identity-${option.id}`}
              >
                {option.label}
              </Button>
            ))}
          </div>
        ) : (
          <ErrorState
            title="Login com Google indisponível"
            description="O provedor de identidade real (Google Identity Platform) ainda não está configurado neste ambiente — item 1.6 do cronograma mestre pendente. Nenhum login é possível agora."
          />
        )}
      </Card>
    </PageContainer>
  );
}
