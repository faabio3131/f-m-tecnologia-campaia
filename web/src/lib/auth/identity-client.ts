/**
 * IdentityClient / IdentityProviderAdapter (Etapa 2, secao 8).
 *
 * Abstracao que futuramente sera ligada ao Google Identity Platform real, quando o
 * item 1.6 (projeto Google Cloud real) for provisionado. Ate la, o modo de producao
 * e sempre `not_configured` -- NUNCA finge que login Google real funciona, NUNCA usa
 * credencial inventada, NUNCA cria bypass.
 *
 * O modo `test` so existe para o harness de E2E (Playwright) e e' controlado
 * explicitamente por `NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE=test` -- nunca o default,
 * nunca setado em build de producao. Mesmo que essa flag fosse ligada por engano em
 * produção, o backend real (sem FIREBASE_PROJECT_ID) usa `AlwaysRejectIdTokenVerifier`
 * e recusaria qualquer id_token de teste -- defesa em profundidade, a autoridade real
 * continua sendo o backend (Etapa 2, secao 6).
 */

export type IdentityClientMode = "not_configured" | "test";

export class IdentityNotConfiguredError extends Error {
  constructor() {
    super(
      "Login com Google Identity Platform ainda nao esta configurado neste ambiente " +
        "(item 1.6 do cronograma mestre pendente). Nenhum login real e possivel agora.",
    );
    this.name = "IdentityNotConfiguredError";
  }
}

export interface IdentityClient {
  readonly mode: IdentityClientMode;
  /** Retorna o ID token verificado pelo provedor. Lanca `IdentityNotConfiguredError`
   * quando `mode === "not_configured"`. */
  signIn(): Promise<string>;
}

class NotConfiguredIdentityClient implements IdentityClient {
  readonly mode = "not_configured" as const;

  async signIn(): Promise<string> {
    throw new IdentityNotConfiguredError();
  }
}

export function createIdentityClient(): IdentityClient {
  // TARGET (item 1.6): quando o projeto Google Cloud real existir, um adapter real
  // (mode "google") sera adicionado aqui, produzindo o id_token via o SDK oficial do
  // Google Identity Platform no navegador. Nao antecipado nesta etapa.
  return new NotConfiguredIdentityClient();
}
