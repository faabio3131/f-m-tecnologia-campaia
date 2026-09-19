# CampaIA — Ponto Zero Web · 06. Roadmap e Work Packages

**Status:** TARGET PROPOSTO — nenhum Work Package foi executado nesta missão.

---

## 1. Reconciliação da sequência sugerida com o CURRENT real

A sequência de 25 blocos sugerida no prompt mestre foi confrontada com `01_CURRENT_E_MATRIZ_CURRENT_TARGET.md`. Ajustes feitos, com justificativa:

- **Fundação do frontend Web** e **design system mínimo** permanecem primeiro — nada os antecede, pois hoje não existe frontend.
- **Autenticação e sessão** vem antes de **contexto de tenant/unidade** na prática — como o domínio de tenancy já está pronto (`permissions.py`), o bloco real de trabalho é a sessão que o alimenta, não o domínio em si.
- **Shell do dashboard** depois de autenticação, não antes — não há por que construir um shell que ninguém pode acessar de forma autenticada.
- **Onboarding**, **Brand Kit**, **briefing**, **estratégia por IA**, **assets**, **aprovação**, **conexões**, **criação de campanha** seguem a ordem do prompt mestre, pois já são as rotas na ordem em que a API as expõe (`GET/POST /brand-profiles` → `POST /connections/oauth/start` → `POST /briefs` → `GET/POST .../plan` → `POST .../validate` → `GET/POST /approvals`).
- **Publicação sandbox** exige adaptador real de ao menos um provider — não pode vir antes de o Work Package de integração existir, mesmo que o prompt mestre a liste antes de "reconciliação"; mantido, mas explicitamente dependente de credenciais de sandbox externas (bloqueio de terceiro, não técnico).
- **Métricas**, **orçamento**, **recomendações**, **otimização limitada** — orçamento já tem API e domínio prontos (`PATCH /budget`); pode, na prática, ser paralelizável ao bloco de aprovação, mas mantido na ordem sugerida para não expandir escopo do roadmap sem necessidade.
- **Hardening, acessibilidade, observabilidade, segurança, staging, produção controlada** — mantidos como fechamento, conforme sugerido, e amarrados aos Gates 6–7 de `05_TESTES_CICD_MIGRACAO.md`.

Nenhum bloco foi executado. Esta é só a reconciliação de ordem, exigida antes de definir os primeiros Work Packages prontos.

---

## 2. Primeiros 5 Work Packages prontos para execução futura

### WP-01 — Fundação do frontend Web

- **Objetivo**: scaffold do projeto Next.js/React (se ADR-0017 aprovada), com lint, typecheck, testes de componente configurados, sem lógica de negócio.
- **Escopo**: estrutura de pastas, configuração de build, CI de frontend (lint+typecheck+build). Nenhuma chamada de rede real ao BFF nesta fase — **verificado nesta correção que `GET /me` (`backend/api/routes_me.py`) exige `require_auth`; não existe hoje nenhum endpoint público/health/readiness no BFF** (`backend/api/main.py`, 21 rotas, todas atrás de autenticação). Consumo do contrato é feito via **mock/fixture local gerado a partir de `contracts/bff-openapi.yaml`** (ex.: resposta de exemplo de `GET /me` fixada como dado estático no frontend), nunca contra o backend real.
- **Fora do escopo**: qualquer tela funcional, autenticação real, dados de produção, qualquer chamada de rede ao BFF.
- **Dependências**: ADR-0017 aprovada.
- **Arquivos/componentes previstos**: novo diretório `web/` (ou equivalente) no repositório canônico; fixtures de contrato (ex.: `web/mocks/`).
- **Contratos afetados**: nenhum — só leitura de `bff-openapi.yaml` para gerar fixtures, sem alteração.
- **Segurança**: nenhuma superfície nova além do que um app estático já expõe. **Garantias explícitas**: nenhum token no bundle; nenhum segredo em variável `NEXT_PUBLIC_*` (ou equivalente exposta ao navegador); nenhuma credencial em `localStorage`; nenhum mecanismo temporário de autenticação que possa migrar acidentalmente para produção — a integração autenticada real só começa no WP-02.
- **Critérios de aceitação**: build reproduzível, lint e typecheck verdes em CI, app roda localmente e renderiza uma tela a partir do mock/fixture de contrato — nenhuma chamada de rede ao BFF ocorre.
- **Testes**: smoke de build; teste de componente trivial contra o mock.
- **Evidências**: log de CI, screenshot local (sem dado sensível, dado é fixture).
- **Riscos**: baixo.
- **Rollback**: remover o diretório novo; nenhum impacto no backend.
- **Gate**: Gate 2 (Scaffold Web).
- **Definição de pronto**: scaffold builda e roda contra fixtures locais, sem lógica de negócio e sem nenhuma chamada de rede real.
- **Autorização necessária**: aprovação da ADR-0017.

### WP-02 — Autenticação e sessão Web real

- **Objetivo**: substituir o token fixo de teste por sessão real (ADR-0018), alimentando `Principal` (`permissions.py`) sem alterar esse módulo.
- **Escopo**: integração com provedor de identidade escolhido, cookies de sessão seguros, CSRF, logout, mapeamento de claims → `roles`/`business_unit_ids`.
- **Fora do escopo**: MFA avançado além do já modelado em `REQUIRES_MFA`; provisionamento de convite de usuário (Work Package futuro).
- **Dependências**: WP-01, ADR-0018 aprovada, provedor de identidade escolhido.
- **Contratos afetados**: `api/deps.py` (troca de mecanismo de autenticação); nenhuma rota de negócio muda de contrato.
- **Segurança**: superfície nova — sessão, CSRF, cookies. Exige revisão de FM Security Engineer antes de fechar.
- **Critérios de aceitação**: login real funciona; rota protegida recusa acesso sem sessão válida; teste automatizado de tentativa cross-tenant confirma `NOT_FOUND`.
- **Testes**: automatizados de CSRF, CORS, step-up, isolamento cross-tenant (novo, na camada Web).
- **Evidências**: suíte de testes de segurança passando; log de CI.
- **Riscos**: alto — é a superfície de autenticação real do produto.
- **Rollback**: manter o BFF capaz de aceitar o token de teste em ambiente de desenvolvimento isolado, nunca em produção.
- **Gate**: Gate 3 (Autenticação).
- **Definição de pronto**: nenhuma rota protegida acessível sem sessão válida; RBAC/ABAC exercitado ponta a ponta pela primeira vez via Web.
- **Autorização necessária**: FM Security Engineer + Diretor.

### WP-03 — Contexto de tenant/unidade e shell do dashboard

- **Objetivo**: resolver tenant/unidade ativa a partir da sessão (nunca de header), construir o shell autenticado do dashboard.
- **Escopo**: seletor de tenant/unidade (quando o usuário pertence a mais de um), layout autenticado, estados vazio/erro/carregando padronizados.
- **Fora do escopo**: qualquer funcionalidade de negócio além da navegação.
- **Dependências**: WP-02.
- **Segurança**: reforço do teste de isolamento cross-tenant do WP-02 no nível de UI (nenhum dado de outro tenant deve aparecer nem transitoriamente).
- **Critérios de aceitação**: troca de tenant/unidade funciona e invalida `step_up_at` (conforme ADR-0018).
- **Testes**: E2E básico de troca de tenant.
- **Riscos**: médio.
- **Rollback**: reverter para tela única sem seletor, se necessário.
- **Gate**: Gate 4 (Tenancy).
- **Definição de pronto**: shell autenticado navega corretamente por tenant/unidade.
- **Autorização necessária**: aprovação de FM Security Engineer no teste de isolamento.

### WP-04 — Onboarding e Brand Kit

- **Objetivo**: primeira jornada funcional real: cadastro de marca, conexão de contas (via `POST /connections/oauth/start`, ainda sem provider real por trás — usar o simulador já citado no domínio).
- **Escopo**: telas de onboarding conforme `13_ESPECIFICACAO_TELAS_APP.md` §3 (fonte funcional, não o código Flutter), consumindo `POST/GET /brand-profiles`, `POST /connections/oauth/start`, `GET /connections`.
- **Fora do escopo**: OAuth real de provider (depende de Work Package de integração, fora desta lista de 5).
- **Dependências**: WP-03.
- **Critérios de aceitação**: usuário completa onboarding e vê Brand Kit salvo; regra de negócio "concluir onboarding habilitado assim que 1 canal conectado" (já era regra do onboarding Flutter, preservada como especificação funcional, não como código) é respeitada.
- **Testes**: E2E de onboarding completo.
- **Riscos**: baixo — usa rotas já existentes e testadas.
- **Rollback**: reverter para estado anterior do shell sem onboarding.
- **Gate**: Gate 5 (Primeira jornada) — parcial, falta briefing/aprovação para completar o gate inteiro.
- **Definição de pronto**: onboarding e Brand Kit funcionais ponta a ponta.
- **Autorização necessária**: FM QA Engineer.

### WP-05 — Briefing, estratégia e aprovação (fecha a primeira jornada crítica)

- **Objetivo**: completar o Gate 5 — briefing → estratégia (IA) → validação → fila de aprovação, com segregação de funções real (usuário distinto aprova).
- **Escopo**: `POST /briefs`, `GET/POST /campaigns/{id}/plan[/regenerate]`, `POST .../validate`, `GET/POST /approvals`, `POST /approvals/{id}/decision`.
- **Fora do escopo**: publicação real (depende de adaptador de provider, fora desta lista).
- **Dependências**: WP-04.
- **Segurança**: segregação de funções já implementada no domínio (`can_approve`); testar na Web que a UI não permite ao próprio proponente aprovar (a API já recusa; a UI deve refletir isso, não substituí-lo).
- **Critérios de aceitação**: jornada completa de briefing até aprovação funciona com dois usuários distintos; tentativa de autoaprovação é recusada visivelmente.
- **Testes**: E2E completo da jornada crítica.
- **Riscos**: médio.
- **Rollback**: reverter para o estado do WP-04.
- **Gate**: Gate 5 (Primeira jornada) — completo.
- **Definição de pronto**: jornada crítica onboarding → briefing → aprovação funciona ponta a ponta com dados simulados.
- **Autorização necessária**: FM QA Engineer + Diretor (fecha Gate 5, abre caminho para Gate 6/Sandbox).

---

## 3. Blocos além do WP-05 (não detalhados como Work Package nesta missão)

Publicação sandbox (depende de credenciais reais de sandbox de ao menos 1 provider — bloqueio externo, não técnico), reconciliação, métricas, orçamento (Web sobre API já pronta), recomendações/otimização limitada, hardening, acessibilidade, observabilidade, segurança formal, staging, produção controlada — todos dependem de decisões e Work Packages anteriores não executados nesta missão. Detalhá-los agora seria antecipar escopo sem o CURRENT que só existirá depois do WP-01 a WP-05.
