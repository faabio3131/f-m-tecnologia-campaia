import type { Me } from "@/contracts/types";

/**
 * LOCAL FIXTURE — WP-01 (Fundação do frontend Web).
 *
 * Dado inteiramente fictício, tipado a partir do schema `Me` de
 * `contracts/bff-openapi.yaml`. Não representa nenhuma sessão, usuário,
 * tenant ou permissão real. Nenhuma chamada de rede ocorre para produzir
 * este valor — ele é um literal estático, carregado localmente.
 *
 * Não deve ser tratado como autenticação, sessão ou integração real.
 * A integração autenticada real começa no WP-02 (ADR-0018).
 */
export const localMeFixture: Me = {
  user_id: "00000000-0000-0000-0000-000000000001",
  tenant_id: "00000000-0000-0000-0000-000000000002",
  business_unit_id: null,
  roles: ["owner"],
  permissions: ["campaign:read", "campaign:approve"],
  mfa_enabled: false,
};
