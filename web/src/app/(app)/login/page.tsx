"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "../../../components/Button";
import { GoogleIdentityButton } from "../../../components/GoogleIdentityButton";
import { Card } from "../../../components/Card";
import { ErrorState } from "../../../components/ErrorState";
import { Input } from "../../../components/Input";
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
  const { status, login, onboardTenant } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [onboardingIdToken, setOnboardingIdToken] = useState<string | null>(null);
  const [companyName, setCompanyName] = useState("");
  const [document, setDocument] = useState("");
  const [segment, setSegment] = useState("");
  const [language, setLanguage] = useState("pt-BR");
  const [timezone, setTimezone] = useState("America/Sao_Paulo");
  const [entryMode, setEntryMode] = useState<"TRIAL" | "PURCHASE">("TRIAL");
  const onboardingIdempotencyKey = useRef<string | null>(null);
  const testMode = isTestIdentityModeEnabled();
  const googleIdentityConfigured = isGoogleIdentityConfigured();

  const rawNext = searchParams.get("next");
  const nextPath =
    rawNext && rawNext.startsWith("/") && !rawNext.startsWith("//") ? rawNext : "/dashboard";

  useEffect(() => {
    if (status === "authenticated") router.replace(nextPath);
  }, [status, nextPath, router]);

  if (status === "bootstrapping") {
    return (
      <PageContainer>
        <Spinner label="Verificando sessão" />
      </PageContainer>
    );
  }

  async function handleIdentitySignIn(idToken: string) {
    setPending(true);
    setError(null);
    setOnboardingIdToken(null);
    try {
      await login(idToken);
    } catch (err) {
      if (err instanceof ApiClientError && err.code === "PERMISSION_DENIED") {
        setError(friendlyLoginError(err));
        setOnboardingIdToken(idToken);
        return;
      }
      setError(friendlyLoginError(err));
    } finally {
      setPending(false);
    }
  }

  async function handleCreateCompany() {
    if (!onboardingIdToken) return;
    if (!companyName.trim() || !segment.trim()) {
      setError("Informe o nome da empresa e o segmento.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      onboardingIdempotencyKey.current ??= "onboard-" + crypto.randomUUID();
      await onboardTenant(
        onboardingIdToken,
        {
          company_name: companyName.trim(),
          document: document.trim() || null,
          segment: segment.trim(),
          language: language.trim() || "pt-BR",
          timezone: timezone.trim() || "America/Sao_Paulo",
          entry_mode: entryMode,
        },
        onboardingIdempotencyKey.current,
      );
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Falha ao criar a empresa.");
    } finally {
      setPending(false);
    }
  }

  return (
    <PageContainer>
      <PageHeader
        title="Entrar no CampaIA"
        description="Identidade via Google; tenant, unidade e permissões são controlados internamente pelo CampaIA."
      />
      <Card className={styles.card}>
        {error ? <ErrorState title="Não foi possível entrar" description={error} /> : null}

        {onboardingIdToken ? (
          <div className={styles.onboardingForm} data-testid="commercial-onboarding-form">
            <div>
              <h2 className={styles.sectionTitle}>Criar sua empresa</h2>
              <p className={styles.testNotice}>
                Sua identidade foi confirmada e ainda não possui um vínculo. A criação do
                tenant só acontece depois desta ação explícita.
              </p>
            </div>
            <Input
              label="Nome da empresa"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              required
            />
            <Input
              label="CNPJ/Documento (quando aplicável)"
              value={document}
              onChange={(e) => setDocument(e.target.value)}
            />
            <Input
              label="Segmento / tipo de negócio"
              value={segment}
              onChange={(e) => setSegment(e.target.value)}
              required
            />
            <Input
              label="Idioma"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
            />
            <Input
              label="Fuso horário"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
            />
            <label className={styles.selectLabel}>
              Entrada comercial
              <select
                className={styles.select}
                value={entryMode}
                onChange={(e) => setEntryMode(e.target.value as "TRIAL" | "PURCHASE")}
              >
                <option value="TRIAL">Teste grátis</option>
                <option value="PURCHASE">Compra/assinatura</option>
              </select>
            </label>
            <div className={styles.actions}>
              <Button
                onClick={handleCreateCompany}
                disabled={pending}
                data-testid="create-commercial-tenant"
              >
                {pending ? "Criando…" : "Criar empresa e continuar"}
              </Button>
              <Button
                variant="secondary"
                onClick={() => setOnboardingIdToken(null)}
                disabled={pending}
              >
                Voltar
              </Button>
            </div>
          </div>
        ) : testMode ? (
          <div className={styles.testOptions}>
            <p className={styles.testNotice}>
              Modo de teste ativo (harness de E2E) — nunca disponível em produção.
            </p>
            {TEST_IDENTITY_OPTIONS.map((option) => (
              <Button
                key={option.id}
                onClick={() => handleIdentitySignIn(option.id)}
                disabled={pending}
                data-testid={"test-identity-" + option.id}
              >
                {option.label}
              </Button>
            ))}
          </div>
        ) : googleIdentityConfigured ? (
          <div className={styles.googleIdentity}>
            <p className={styles.testNotice}>
              Continue com sua Conta Google. O CampaIA usa a identidade apenas para
              autenticar você; tenant, unidade e permissões continuam controlados pelo
              próprio CampaIA.
            </p>
            <GoogleIdentityButton
              disabled={pending}
              onIdToken={handleIdentitySignIn}
              onError={setError}
              text="continue_with"
            />
          </div>
        ) : (
          <ErrorState
            title="Login com Google não configurado"
            description="A configuração pública do Google Identity Platform ainda não está disponível neste ambiente. O acesso permanece fail-closed."
          />
        )}
      </Card>
    </PageContainer>
  );
}
