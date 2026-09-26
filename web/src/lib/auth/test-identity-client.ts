/**
 * Harness EXCLUSIVO de teste/E2E (Etapa 2, secao 9) -- NUNCA importado fora de
 * `/login` sob `NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE=test`. Nao adiciona bypass algum:
 * o `id_token` fixo escolhido aqui ainda precisa passar pelo protocolo REAL de
 * `POST /auth/session` contra o backend real, que so o aceita se o
 * `DeterministicTestIdTokenVerifier` do harness de backend
 * (`backend/tests_support/e2e_identity.py`) estiver ativo -- nunca em produção real,
 * onde o backend usa `AlwaysRejectIdTokenVerifier` ou o adapter real do Google.
 *
 * Os valores abaixo devem corresponder EXATAMENTE aos definidos em
 * `backend/tests_support/e2e_identity.py`.
 */
export const TEST_IDENTITY_MODE_ENV_VALUE = "test";

export interface TestIdentityOption {
  id: string;
  label: string;
}

export const TEST_IDENTITY_OPTIONS: readonly TestIdentityOption[] = [
  { id: "e2e-test-id-token-tenant-a-owner", label: "Owner — tenant A (demo-tenant)" },
  { id: "e2e-test-id-token-tenant-b-owner", label: "Owner — tenant B (other-tenant)" },
  { id: "e2e-test-id-token-unverified-email", label: "E-mail não verificado (deve falhar)" },
  { id: "e2e-test-id-token-unknown-email", label: "E-mail sem vínculo interno (deve falhar)" },
  {
    id: "e2e-test-id-token-multi-tenant-owner",
    label: "Owner — dois vínculos (demo-tenant + other-tenant)",
  },
];

export function isTestIdentityModeEnabled(): boolean {
  return process.env.NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE === TEST_IDENTITY_MODE_ENV_VALUE;
}
