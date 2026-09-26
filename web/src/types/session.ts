/**
 * Reexporta os tipos de sessao/vinculos gerados de `contracts/bff-openapi.yaml`
 * (Fase 1 do painel mestre, 25/09/2026: `/auth/session`, `/me/memberships` e
 * `/auth/session/switch` foram documentados no contrato, fechando a pendencia
 * registrada na Etapa 2 -- antes deste arquivo tinha tipos manuais espelhando
 * `backend/api/models.py` a mao).
 */
export type { SessionUser, Membership, MembershipsResponse } from "../contracts/types";
