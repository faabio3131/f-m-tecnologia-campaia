/**
 * Tipos manuais MINIMOS para o contrato de sessao real (POST/GET/DELETE
 * /auth/session, backend/api/routes_auth.py + backend/api/models.py::SessionLoginResponse).
 *
 * PENDENCIA registrada (Etapa 2, secao 24): `contracts/bff-openapi.yaml` ainda NAO
 * documenta `/auth/session` -- so `/me` esta no contrato hoje. Os campos abaixo
 * espelham exatamente `SessionLoginResponse` (backend/api/models.py), nada inventado.
 * Quando o contrato for atualizado (fora do escopo desta missao, que nao altera
 * `contracts/`), migrar para tipos gerados via `openapi-typescript`.
 */
export interface SessionUser {
  user_id: string;
  tenant_id: string;
  business_unit_id: string | null;
  roles: string[];
  /** So existe em memoria no cliente -- nunca localStorage/sessionStorage. */
  csrf_token: string;
}
