# EVIDÊNCIA — F0 / WP-F00-01 — Reconciliação CURRENT e SSOT

**Data:** 27/09/2026  
**Status:** DONE_VERIFIED — reconciliação documental interna certificada com CI real verde; Gate G0 fechado.  
**Repo:** faabio3131/f-m-tecnologia-campaia  
**PR:** #31 — reconciliation/campaia-final-takeover → main

## CURRENT confirmado antes da alteração

- PR #31: open, draft=true, merged=false, mergeable=true.
- Base: main@851db13723c3575d516bed64d71535cd7fed8bca.
- HEAD: f30f76bc44a20966795e45c1eee305aee2ea78dd.
- GitHub Actions: backend success; frontend success; session-protocol E2E real/cross-tenant success — 3 jobs verdes.
- O shell desta sessão não conseguiu resolver github.com para clone. Portanto não foi inventado git status local. A alteração é feita pela API Git diretamente sobre o SHA imutável da branch, com fast-forward sem force; não há working tree local mutável participando do commit.

## Contradições encontradas

1. Cronograma antigo de 24/09 ainda se apresentava como mestre de 3 etapas/prompts.
2. Matriz Web antiga dizia Web/auth inexistentes.
3. Painéis antigos com “VIGENTE” podiam ser confundidos com CURRENT.
4. FUNCTIONAL_REQUIREMENTS dizia IMPLEMENTADO embora vários F1–F10 sejam TARGET/PARTIAL.
5. Especificação de telas se declarava mobile-only e Web fora de escopo.
6. Product Charter continha trechos históricos já substituídos.
7. NFR de sessão JWT conflita com ADR-0018/0022.
8. Não existia matriz ligando F1–F10, NFRs e telas aos WPs F0–F20.

## Reconciliação aplicada

- Banners SUPERSEDED/precedência sem apagar histórico.
- Controle mestre F0–F20 criado no repositório.
- Matriz Mestre de Cobertura criada.
- Registro de fontes SUPERSEDED criado.
- Nenhuma regra de negócio ou código executável alterado.

## Tenants de homologação

Ordem reportada pelo Diretor:
1. Nova FM Tecnologia — criada primeiro.
2. FM Tecnologia — criada depois.

Ambas devem operar como tenants comuns. Nenhuma recebe branch, código, variável de ambiente, Customer ID global, token manual, seed privilegiado ou bypass.

## Google Ads / Google Cloud

FATO confirmado na arquitetura/código: OAuth server-side multi-tenant, refresh token no Vault por SecretRef, Customer ID por conexão; MCC interno da Nova FM não é obrigatório para clientes.

FATO reportado ainda não verificado por console/API externa: projeto campaia-google-ads-integration e ativos Google associados.

Status: EXTERNAL_INFRASTRUCTURE / EXTERNAL_CREDENTIAL até confirmação do projeto, billing, OAuth Web Client, redirect URI, developer-token access level e contas externas. Esses itens são gates obrigatórios de F8/F9/F19; documentação não os promove.

## Web x Mobile

ADR-0016 aprovada: Web é a linha comercial. Mobile permanece em quarentena e não será evoluído sem HUMAN_DECISION.

## Fora de escopo

Sem F1+, sem credenciais, sem GCP, sem merge, sem deploy, sem produção e sem mutação em contas externas.

## Aceite e rollback

Aceite: arquivos no novo HEAD + CI do repositório novamente verde. Rollback: revert do commit documental; não houve migração nem efeito externo.


## Certificação pós-alteração

Commit certificado: ff1d6d95ec8f5ecdab807cb46e56fce0328d7d08.

- CAMPAIA Backend Tests — run 117: success.
- CAMPAIA Frontend Tests — run 55: success.
- Job “Run unit + API test suites”: success.
- Job “Lint, typecheck, contract/security boundaries, unit+component tests, build, E2E smoke”: success.
- Job “Real session protocol E2E (backend real + frontend real, cross-tenant obrigatorio)”: success.

**Gate G0: DONE_VERIFIED.** Não há contradição ativa identificada entre CURRENT, cronograma F0–F20 e fontes normativas capaz de orientar uma implementação para arquitetura errada. Itens Google Cloud/Ads não verificáveis nesta sessão continuam explicitamente EXTERNAL_INFRASTRUCTURE / EXTERNAL_CREDENTIAL para os gates próprios.
