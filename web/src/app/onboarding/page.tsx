import { Badge } from "@/components/Badge";
import { BrandKitForm } from "@/components/BrandKitForm";
import { Card } from "@/components/Card";
import { ConnectAccountCard } from "@/components/ConnectAccountCard";
import { ErrorState } from "@/components/ErrorState";
import { PageContainer } from "@/components/PageContainer";
import type { Capability } from "@/contracts/types";
import {
  getPublicBffOrigin,
  getServerBrandProfiles,
  getServerConnectionCapabilities,
  getServerConnections,
  getServerSession,
} from "@/lib/session";
import styles from "./page.module.css";

const CONNECT_PROVIDERS = [
  { provider: "GOOGLE_ADS" as const, label: "Google Ads" },
  { provider: "META" as const, label: "Meta (Facebook/Instagram)" },
  { provider: "WHATSAPP" as const, label: "WhatsApp Business" },
];

/**
 * WP-04: primeira jornada funcional real -- Brand Kit (POST/GET /brand-profiles) e conectar
 * contas (POST /connections/oauth/start+complete, GET /connections), conforme
 * docs/product/13_ESPECIFICACAO_TELAS_APP.md §3.4/§4. WP-09 completa o ciclo de vida da
 * conexão: desconectar (DELETE /connections/{id}) e ver capacidades reais (GET
 * /connections/{id}/capabilities, buscadas aqui no servidor para cada conexão ativa --
 * mesmo padrão de toda outra leitura desta aplicação, nunca no cliente).
 *
 * Fora do escopo, deliberadamente: cadastro de empresa/CNPJ e unidade de negócio (§3.2/
 * §3.3 do mesmo documento) -- nenhum endpoint de criação de tenant/unidade existe no
 * backend hoje (tenant_id vem sempre da sessão autenticada, nunca é criado via API); essas
 * duas telas descrevem um TARGET que este Work Package não constrói, para não fabricar uma
 * tela sem chamada de rede real por trás dela.
 */
export default async function OnboardingPage() {
  const bffOrigin = getPublicBffOrigin();

  if (!bffOrigin) {
    return (
      <PageContainer>
        <Card>
          <ErrorState
            title="Não configurado"
            description="A variável de ambiente NEXT_PUBLIC_CAMPAIA_BFF_ORIGIN não está definida — o onboarding não sabe onde está o backend (BFF)."
          />
        </Card>
      </PageContainer>
    );
  }

  const me = await getServerSession();
  if (!me) {
    const loginUrl = `${bffOrigin}/auth/login?redirect_after_login=${encodeURIComponent("/onboarding")}`;
    return (
      <PageContainer>
        <header className={styles.header}>
          <Badge tone="neutral">CampaIA Web — Onboarding (WP-04)</Badge>
          <h1 className={styles.title}>Você não está autenticado</h1>
        </header>
        <Card>
          <a className={styles.loginLink} href={loginUrl}>
            Entrar
          </a>
        </Card>
      </PageContainer>
    );
  }

  const [brandProfiles, connections] = await Promise.all([
    getServerBrandProfiles(),
    getServerConnections(),
  ]);

  if (brandProfiles === null || connections === null) {
    return (
      <PageContainer>
        <Card>
          <ErrorState
            title="Não foi possível carregar os dados do onboarding"
            description="GET /brand-profiles ou GET /connections falhou apesar de uma sessão válida existir. Tente recarregar a página."
          />
        </Card>
      </PageContainer>
    );
  }

  // WP-09: capabilities only exist for a connection that is actually connected -- fetched
  // server-side, same as every other read in this app, never client-side. `id` is typed
  // optional by the generated contract types (same as Campaign.id elsewhere) but always
  // present in the real response.
  const activeConnections = connections.filter((c) => c.status === "ACTIVE");
  const capabilitiesEntries = await Promise.all(
    activeConnections.map(async (c) => {
      const connectionId = c.id as string;
      return [connectionId, await getServerConnectionCapabilities(connectionId)] as const;
    }),
  );
  const capabilitiesByConnectionId = new Map<string, Capability[] | null>(capabilitiesEntries);

  // Roadmap WP-04: "Concluir Onboarding habilitada assim que pelo menos um canal estiver
  // conectado" -- the same rule the pre-existing Flutter onboarding used, preserved here as
  // a functional rule, not as ported code. There is no "onboarding_completed" flag to set
  // server-side (no such endpoint exists) -- completing onboarding just means the user is
  // done with this flow and moves on to the authenticated shell.
  const canFinishOnboarding = connections.length > 0;

  return (
    <PageContainer>
      <header className={styles.header}>
        <Badge tone="accent">CampaIA Web — Onboarding (WP-04)</Badge>
        <h1 className={styles.title}>Bem-vindo, {me.user_id}</h1>
      </header>

      <Card>
        <h2 className={styles.sectionTitle}>Conectar contas</h2>
        <p className={styles.sectionNote}>
          Cada conexão é opcional individualmente — você pode continuar tendo conectado
          apenas um canal.
        </p>
        <div className={styles.connectGrid}>
          {CONNECT_PROVIDERS.map(({ provider, label }) => {
            const connection = connections.find((c) => c.provider === provider);
            return (
              <ConnectAccountCard
                key={provider}
                bffOrigin={bffOrigin}
                provider={provider}
                label={label}
                connection={connection}
                capabilities={
                  connection ? capabilitiesByConnectionId.get(connection.id as string) : undefined
                }
              />
            );
          })}
        </div>
      </Card>

      <Card>
        <h2 className={styles.sectionTitle}>Brand Kit</h2>
        <BrandKitForm bffOrigin={bffOrigin} existing={brandProfiles} />
      </Card>

      <Card>
        {canFinishOnboarding ? (
          <a className={styles.finishLink} href="/dashboard">
            Concluir Onboarding
          </a>
        ) : (
          <p className={styles.finishDisabledNote}>
            Conecte ao menos uma conta para concluir o onboarding.
          </p>
        )}
      </Card>
    </PageContainer>
  );
}
