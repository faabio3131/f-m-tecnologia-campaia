# EVIDÊNCIA — F2 IAM, RBAC E ORGANIZAÇÃO / G2 — 28/09/2026

**WP:** WP-F02-01  
**Fase/Gate:** F2 / G2  
**Status oficial:** `PARTIAL`  
**Repositório:** `faabio3131/f-m-tecnologia-campaia`  
**Branch:** `reconciliation/campaia-final-takeover`  
**HEAD funcional certificado:** `54a3082e59d8db821a8df51051d87331484c1c18`

## 1. CURRENT antes da alteração

O CURRENT já possuía:
- matriz RBAC/ABAC com OWNER, ADMIN, FINANCE, APPROVER, MARKETER e VIEWER;
- escopo por tenant e business unit;
- step-up server-side ligado à sessão, identidade e `auth_time`;
- segregação proposer/approver;
- revogação de sessão na desativação de membership;
- onboarding/convite/lifecycle de F1.

As lacunas reais de F2 eram:
- ausência de CRUD comercial de business units;
- ausência de edição comercial de papéis/unidade de membership;
- tela de Usuários deliberadamente bloqueada fora do harness de teste para mutações sensíveis;
- ausência de superfície Web de Organização;
- ausência de prova explícita de ownership transfer;
- ausência de prova de persistência das estruturas organizacionais após restart;
- novas rotas ainda não existiam no contrato OpenAPI.

## 2. Implementação

### Backend

Foram adicionadas rotas tenant-scoped, sem aceitar `tenant_id` do cliente:
- `GET /business-units`;
- `POST /business-units`;
- `PATCH /business-units/{businessUnitId}`;
- `POST /business-units/{businessUnitId}/deactivate`;
- `POST /business-units/{businessUnitId}/reactivate`;
- `PATCH /memberships/{membershipId}`.

Mutações exigem CSRF, step-up e Idempotency-Key. Alteração de papel/unidade revoga as sessões do membership e grava auditoria.

### Guardrails

- Admin não pode editar/conceder Owner;
- último Owner ativo não pode perder Owner;
- ownership transfer exige sucessor Owner antes da demissão do Owner atual;
- unidade com membro ativo não pode ser desativada;
- última unidade ativa não pode ser desativada;
- unidade alvo de membership precisa existir, estar ativa e pertencer ao mesmo tenant;
- cross-tenant retorna 404 sem enumerar recursos;
- replay idempotente não duplica efeito;
- business-unit isolation operacional preexistente foi preservado.

Durante a primeira implementação, uma tentativa de tornar Owner/Admin tenant-wide no `Principal` operacional fez 5 invariantes antigos de business-unit isolation falharem no Backend #134. A causa raiz foi identificada e a ampliação foi removida no commit `5ccbb462e748259d01b10d9aca72d2a7fc690462`. O backend voltou a respeitar o escopo operacional original e passou no Backend #135. O achado foi tratado como regressão real, não mascarado por alteração de testes.

### Web

- nova tela `/settings/organization`;
- tela `/settings/users` agora administra convite, papel, unidade, desativação e reativação;
- navegação de Owner/Admin expõe Organização e Usuários;
- reautenticação administrativa usa o mesmo fluxo Google Identity Platform real;
- token de reautenticação permanece somente em memória e é descartado após a prova;
- a elevação subsequente é reconhecida como janela server-side da sessão, sem reter token no browser;
- sem configuração Google externa, UI permanece fail-closed e informa a pendência.

## 3. Provas automatizadas adicionadas

A suíte F2 comprova:
1. criar, listar e renomear unidade;
2. replay idempotente de criação;
3. bloqueio de desativação de unidade em uso;
4. alteração de papel/unidade + revogação da sessão anterior;
5. Admin não concede/administra Owner;
6. último Owner não pode se rebaixar;
7. transferência de ownership em sequência segura;
8. mutação cross-tenant de unidade/membership retorna 404;
9. alteração de acesso gera auditoria;
10. unidades, memberships e papéis sobrevivem restart do backend;
11. E2E Web cria segunda unidade, convida usuário nessa unidade, altera VIEWER→MARKETER, comprova revogação/relogin e preserva lifecycle.

## 4. Contrato

`contracts/bff-openapi.yaml` passou a documentar as rotas e schemas de F2. O arquivo `web/src/contracts/bff-openapi.generated.ts` foi obtido do próprio artefato canônico gerado pelo CI. O Git blob criado localmente no GitHub foi verificado como exatamente `6331e3d42eeac3179f17ad9e9dd5396737c84749`, igual ao artefato esperado. No HEAD funcional final, `contracts:check` passou.

## 5. CI final do HEAD funcional

### Backend #143 — success
- 377 testes de domínio;
- 252 testes de API;
- `pip-audit`: nenhuma vulnerabilidade conhecida;
- AsyncAPI: 24 eventos verificados end-to-end.

### Frontend #81 — success
- `npm audit`: 0 vulnerabilidades;
- lint: success;
- typecheck strict: success;
- contract drift: success;
- security boundary: success;
- 21 arquivos / 72 testes Vitest: success;
- production build: success;
- 4 smoke E2E: success;
- 27 E2E cross-stack backend real + frontend real: success.

## 6. Limite da evidência

O ambiente externo necessário para homologar Google Login/step-up real ainda não existe. Por decisão do Diretor, deploy e teste com conta Google real foram adiados.

Classificação:
- configuração/homologação Google: `EXTERNAL_INFRASTRUCTURE` / `EXTERNAL_CREDENTIAL`;
- F2/WP-F02-01: `PARTIAL`;
- G2: aberto;
- PostgreSQL/multi-réplica/atomicidade produtiva: F3/F4, `PRODUCTION_GATE`/TARGET.

Sucesso no harness determinístico não é apresentado como homologação Google real.

## 7. Governança

- PR #31 permanece Draft;
- nenhum merge;
- nenhum deploy;
- nenhuma alteração de produção;
- Nova FM Tecnologia e FM Tecnologia não receberam qualquer caminho privilegiado ou hardcode.
