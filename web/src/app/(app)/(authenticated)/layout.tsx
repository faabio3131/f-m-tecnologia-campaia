"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { AppShell } from "../../../components/AppShell";
import { PageContainer } from "../../../components/PageContainer";
import { Spinner } from "../../../components/Spinner";
import { ErrorState } from "../../../components/ErrorState";
import { useAuth } from "../../../providers/AuthProvider";

/**
 * Route guard real (Etapa 2, secao 22). A autoridade e' `GET /auth/session`
 * (via AuthProvider), nunca a mera presenca do cookie -- cookie presente != sessao
 * valida. Durante bootstrap renderiza carregamento, nunca conteudo privado; se a
 * sessao for invalida, redireciona para /login preservando a rota de retorno.
 */
export default function AuthenticatedLayout({ children }: { children: ReactNode }) {
  const { status, session, me, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "unauthenticated") {
      const next = encodeURIComponent(pathname);
      router.replace(`/login?next=${next}`);
    }
  }, [status, pathname, router]);

  if (status === "bootstrapping") {
    return (
      <PageContainer>
        <Spinner label="Verificando sessão" />
      </PageContainer>
    );
  }

  if (status === "error") {
    return (
      <PageContainer>
        <ErrorState
          title="Não foi possível verificar sua sessão"
          description="Ocorreu um problema de comunicação com o servidor. Tente recarregar a página."
        />
      </PageContainer>
    );
  }

  if (status === "unauthenticated" || !session || !me) {
    // Redirecionamento ja disparado pelo efeito acima -- nao renderiza nenhum
    // conteudo privado enquanto a navegacao nao acontece (nunca "pisca" dado
    // de sessao anterior).
    return (
      <PageContainer>
        <Spinner label="Redirecionando para o login" />
      </PageContainer>
    );
  }

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  return (
    <AppShell
      user={{
        userId: session.user_id,
        tenantId: session.tenant_id,
        businessUnitId: session.business_unit_id,
        roles: me.roles ?? [],
      }}
      onLogout={handleLogout}
    >
      {children}
    </AppShell>
  );
}
