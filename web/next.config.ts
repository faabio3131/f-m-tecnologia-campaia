import type { NextConfig } from "next";

/**
 * Proxy same-origin para o BFF do CampaIA (Etapa 2, secao 11).
 *
 * `CAMPAIA_BFF_ORIGIN` e' lida so no servidor (Next.js), nunca exposta via
 * `NEXT_PUBLIC_*` -- o navegador so ve `/api/campaia/*`, nunca a origem real do
 * backend. Rewrite nativo do Next (nao um Route Handler custom): testado
 * empiricamente (curl real) que preserva `Set-Cookie`, cookie enviado de volta,
 * `Origin`, `X-CSRF-Token`, status code e corpo da resposta sem modificacao --
 * suficiente para o protocolo de sessao real, sem inventar complexidade adicional
 * (secao 11: "se rewrite nativo atender, preferir a solucao mais simples").
 */
const nextConfig: NextConfig = {
  async rewrites() {
    const origin = process.env.CAMPAIA_BFF_ORIGIN;
    if (!origin) {
      // Build/CI da pagina de fundacao (WP-01) nao depende do BFF -- nunca um
      // default hardcoded, so ausencia explicita de rewrite quando nao configurado.
      // Dev local e E2E devem configurar CAMPAIA_BFF_ORIGIN (ver web/.env.example).
      console.warn(
        "[campaia] CAMPAIA_BFF_ORIGIN nao configurada -- /api/campaia/* nao sera " +
          "roteada para nenhum backend.",
      );
      return [];
    }
    return [
      {
        source: "/api/campaia/:path*",
        destination: `${origin}/:path*`,
      },
    ];
  },
};

export default nextConfig;
