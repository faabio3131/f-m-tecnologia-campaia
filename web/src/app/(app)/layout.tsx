import type { ReactNode } from "react";
import { AuthProvider } from "../../providers/AuthProvider";

/**
 * Grupo de rotas `(app)` -- unico ponto que monta `AuthProvider` (Etapa 2).
 *
 * Deliberadamente NAO no layout raiz (`app/layout.tsx`): a pagina de fundacao
 * do WP-01 (`app/page.tsx`, rota `/`) tem um teste E2E certificado que exige ZERO
 * chamadas de rede ao BFF (`e2e/foundation.spec.ts`) -- montar o AuthProvider ali
 * dispararia o bootstrap (`GET /auth/session`) e quebraria essa garantia. `/login`
 * e as rotas autenticadas vivem sob este grupo (nao adiciona segmento na URL).
 */
export default function AppGroupLayout({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}
