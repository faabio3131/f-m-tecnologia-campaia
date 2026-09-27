# CampaIA — CONTROLE MESTRE DE EXECUÇÃO F0–F20

**Data-base:** 27/09/2026  
**Status:** PARTIAL — F0 em fechamento; não implica merge, deploy ou produção.  
**Repositório canônico:** faabio3131/f-m-tecnologia-campaia  
**Linha de trabalho:** PR #31, branch reconciliation/campaia-final-takeover  
**Fonte mestra:** “CAMPAIA - CRONOGRAMA MESTRE DE EXECUCAO TOTAL ATE PRONTO COMERCIAL”, v1.0, 27/09/2026.

## 1. Ordem de autoridade

1. CURRENT técnico real do repositório, PR, CI e comportamento.
2. Cronograma Mestre F0–F20 / G0–G20.
3. ADRs e decisões vigentes.
4. Evidências reproduzíveis.
5. Documentação histórica apenas como contexto.

Nenhum painel antigo ou afirmação anterior substitui CURRENT. Status oficiais: DONE_VERIFIED, PARTIAL, TARGET, HUMAN_DECISION, EXTERNAL_CREDENTIAL, EXTERNAL_INFRASTRUCTURE, EXTERNAL_APPROVAL, PRODUCTION_GATE, BLOCKED e SUPERSEDED.

## 2. CURRENT de entrada do WP-F00-01

- PR #31: aberta, Draft, não mergeada e mergeable.
- Base: main@851db13723c3575d516bed64d71535cd7fed8bca.
- HEAD de entrada: f30f76bc44a20966795e45c1eee305aee2ea78dd.
- CI desse HEAD: backend verde; frontend verde; E2E de sessão real/cross-tenant verde — 3 jobs verdes.
- ADR-0016: Web é a linha comercial; mobile permanece em quarentena.
- Simulador, sandbox, staging, homologação e produção permanecem estados diferentes.
- Merge, deploy, produção, GO/NO-GO e HUMAN_DECISION exigem autorização expressa do Diretor.

## 3. Caminho crítico

F0 → F1/F2 → F3/F4 → F5 → F6/F7 → F8/F9 → F10 → F11 → F12–F14 → F15 → F16–F17 → F18 → F19 → F20.

| Fase | Gate | Escopo principal | Estado base |
|---|---|---|---|
| F0 | G0 | CURRENT + SSOT + cobertura + superseded | PARTIAL |
| F1 | G1 | Trial/onboarding/tenant/unidade/usuários | TARGET |
| F2 | G2 | Multi-tenancy/RBAC/step-up/isolamento | PARTIAL |
| F3 | G3 | Atomicidade/idempotência/concorrência | PRODUCTION_GATE |
| F4 | G4 | Persistência/infra/segredos/observabilidade-base | TARGET |
| F5 | G5 | Billing/trial/planos/admin comercial | PARTIAL |
| F6 | G6 | Brand Kit/assets/storage | TARGET |
| F7 | G7 | Briefing→IA→policy→preview→approval | PARTIAL |
| F8 | G8 | Google Ads — PLATFORM + OAuth por tenant | EXTERNAL_INFRASTRUCTURE |
| F9 | G9 | Google Ads — adaptador/publicação real | TARGET |
| F10 | G10 | Meta — conexão/publicação real | TARGET |
| F11 | G11 | WhatsApp Business real | TARGET |
| F12 | G12 | Orquestração real, replay, compensação | TARGET |
| F13 | G13 | Métricas/otimização governada | TARGET |
| F14 | G14 | Administração/configuração/auditoria | TARGET |
| F15 | G15 | Visual Premium completo | TARGET |
| F16 | G16 | Segurança/LGPD/hardening | TARGET |
| F17 | G17 | Performance/resiliência/DR/observabilidade | TARGET |
| F18 | G18 | Staging/homologação E2E | TARGET |
| F19 | G19 | Produção — GO/NO-GO | PRODUCTION_GATE |
| F20 | G20 | Comercialmente disponível | TARGET |

## 4. Invariantes

- SaaS multi-tenant real; Nova FM Tecnologia e FM Tecnologia são tenants comuns de homologação.
- PLATFORM e TENANT são configurações distintas.
- Segredo de tenant permanece no Vault/Secret Manager e domínio usa SecretRef.
- Mutação crítica cobre happy path, negative path, replay/idempotência e cross-tenant; quando aplicável restart, concorrência e multi-worker.
- Campanha nova exige aprovação humana; automação limitada não autoriza publicação inicial.
- Nenhum segredo real entra no Git.
- Visual Premium integral ocorre após o fechamento funcional principal.

## 5. Jornada comercial obrigatória

Compra/trial → tenant → usuários/unidades → Google/Meta/WhatsApp → Brand Kit → briefing → estratégia/criativos IA → policy/preview → aprovação → publicação real → métricas → otimização governada → cobrança/administração, sem intervenção de desenvolvedor como fluxo normal.

## 6. Retomada

Toda retomada relevante deve registrar CURRENT, Fase/Gate, DONE_VERIFIED preservado, blockers, WP exato e evidências. A matriz canônica está em docs/CAMPAIA_MATRIZ_MESTRE_COBERTURA_20260927.md.
