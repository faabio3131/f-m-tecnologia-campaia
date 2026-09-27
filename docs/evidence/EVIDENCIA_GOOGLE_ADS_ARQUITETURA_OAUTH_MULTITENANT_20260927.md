# CampaIA — Google Ads: reaproveitamento de ativos e arquitetura-alvo OAuth multi-tenant

**Data:** 27/09/2026 · **Branch:** `reconciliation/campaia-final-takeover` (PR #31).
**Natureza deste documento:** registro de decisões e fatos reportados pelo Diretor sobre
ativos de infraestrutura Google Ads/Cloud, mais a reconciliação da arquitetura-alvo de
credenciais para este canal. **Documental apenas** — nenhuma linha de código foi alterada
nesta tarefa; nenhum adaptador Google Ads real foi iniciado; nenhuma credencial real foi
criada, lida ou registrada em texto plano aqui.

## Protocolo antialucinação aplicado

Os itens da seção "REAPROVEITAR" abaixo são **relatados pelo Diretor**, não verificados
por Claude — esta sessão não tem acesso ao Google Cloud Console nem ao Google Ads Manager
(mesma limitação já registrada em `CHECKLIST_CADASTROS_PLATAFORMAS_20260827.md` e em
`DIRETOR_MARCO_GOOGLE_ADS_MANAGER_CRIADO_20260827.md`). Marcados como `FATO REPORTADO
(NÃO VERIFICADO POR CLAUDE)`. Confirmado por leitura real do código nesta sessão (`grep`
em `backend/`, 27/09/2026): não existe hoje nenhum env var Google-Ads-específico
(`GOOGLE_ADS_CUSTOMER_ID`, `GOOGLE_ADS_LOGIN_CUSTOMER_ID`, developer token) nem nenhum
adaptador real do Google Ads no código — a única referência a esses termos é o padrão de
redação (`campaia_core/ai_gateway.py`, sanitizador de logs) que já trata
`developer_token`/`refresh_token`/`access_token`/`client_secret` como segredo, nunca
logado. **FATO CONFIRMADO.**

## REAPROVEITAR (ativos relatados pelo Diretor, não verificados por Claude)

| Ativo | Papel | Observação |
|---|---|---|
| `campaia-google-ads-integration` | Candidato a Cloud Project oficial do CampaIA | `FATO REPORTADO` — nome de projeto GCP, não confirmado via API/Console por Claude |
| Nova FM Tecnologia — Gerenciadora | Conta gerenciadora (MCC) de homologação/administração | `FATO REPORTADO`. **Decisão explícita do Diretor, reafirmada aqui:** esta conta gerenciadora **nunca é um MCC obrigatório por cliente** — é uma conta interna da Nova FM para homologar e administrar, não um vínculo que todo tenant precisa ter |
| Conta Google Ads criada ontem (26/09/2026) | Conta de teste/homologação | `FATO REPORTADO`. Regra explícita: esta conta **deve, no futuro, entrar no CampaIA como um tenant comum, via OAuth** — nunca como conta privilegiada/especial no modelo de dados ou no código |
| OAuth Desktop Client (existente) | Uso manual/teste apenas | `FATO REPORTADO`. **Decisão explícita: manter só para teste/manual — NUNCA usar como credencial OAuth comercial.** Um Desktop Client não suporta o fluxo de redirect server-side (`authorization_code` + `state` + callback HTTPS) que a arquitetura server-side exige (ver ADR-0013) |

### Reconciliação: conta gerenciadora "antiga" x "nova"

`docs/evidence/DIRETOR_MARCO_GOOGLE_ADS_MANAGER_CRIADO_20260827.md` registra uma conta
gerenciadora criada em 27/08/2026 com nome **"F&M Tecnologia"**, ID **975-498-3401**. A
instrução de hoje (27/09/2026) nomeia a conta gerenciadora vigente como **"Nova FM
Tecnologia — Gerenciadora"**.

**NÃO VERIFICADO POR CLAUDE se são a mesma conta renomeada (consistente com o
rebranding institucional F&M Tecnologia → Nova FM Tecnologia, já refletido em
`CLAUDE.md`/`docs/nova-fm/`) ou uma conta gerenciadora genuinamente nova, distinta da de
27/08/2026.** Claude não tem acesso ao Google Ads Manager para confirmar o ID da conta
atual. **PENDÊNCIA:** o Diretor confirmar explicitamente, numa próxima interação, se
`975-498-3401` é o ID atual da "Nova FM Tecnologia — Gerenciadora" (rename) ou se essa
conta foi substituída/aposentada por uma diferente — este documento não assume nenhuma
das duas hipóteses.

## CRIAR/CORRIGIR (arquitetura-alvo — TARGET, não implementada nesta tarefa)

Reafirma e detalha o TARGET já registrado no Adendo de 27/09/2026 da ADR-0013 (troca de
OAuth server-side), agora especificamente para Google Ads:

1. **OAuth Client tipo "Web Application"** — credencial **PLATFORM** (Client ID/Secret do
   app CampaIA perante o Google, centralizada por ambiente, nunca por tenant). Distinta
   do OAuth Desktop Client existente (mantido só para teste/manual, nunca comercial —
   ver tabela acima).
2. **Redirect URI oficial do CampaIA** — também **PLATFORM**: o domínio de callback HTTPS
   publicado que o fluxo server-side exige (mesma pendência já registrada como
   `EXTERNAL_INFRASTRUCTURE` na ADR-0013 — depende da Web da Nova FM estar em produção
   com domínio publicado).
3. **OAuth multi-user:** cada tenant autoriza a própria conta Google Ads via OAuth —
   nunca um vínculo MCC obrigatório com a conta gerenciadora da Nova FM. A conta
   gerenciadora (item REAPROVEITAR acima) serve para homologação/administração da Nova
   FM, não para operar contas de clientes por MCC.
4. **Refresh tokens por tenant → Credential Vault.** Já construído e testado
   (`campaia_core/credential_vault.py`, `api/repositories.py::VaultRepository`, Adendo
   27/09/2026 da ADR-0013) — nenhum trabalho de engenharia novo necessário para este
   ponto especificamente; a troca real de OAuth (item 2) é o que falta para popular o
   Vault via o fluxo comercial real, em vez do mecanismo dev-only atual
   (`POST /connections/{id}/dev-attach-credential`, ver Achado 4 da auditoria
   independente #3, 27/09/2026).
5. **Customer IDs escolhidos dinamicamente, nunca em env var global.** Reafirma a
   correção já registrada no Adendo da ADR-0013 (a conta de teste do Diretor havia sido
   configurada via `GOOGLE_ADS_CUSTOMER_ID`/`GOOGLE_ADS_LOGIN_CUSTOMER_ID` como se fosse
   arquitetura comercial — corrigido pelo Diretor). **Confirmado por leitura do código
   nesta sessão: esses env vars não existem hoje no código** (ver seção "Protocolo
   antialucinação" acima) — a correção já está refletida no CURRENT, este documento só
   formaliza a regra por escrito para o adaptador real futuro: o Customer ID de cada
   conexão vem do `Connection`/`SecretRef` daquele tenant, resolvido em tempo de
   execução, nunca de configuração de processo.

**Nada do item "CRIAR/CORRIGIR" foi implementado nesta tarefa.** Nenhum OAuth Client Web
foi criado (ação de Google Cloud Console, fora do alcance de Claude). Nenhum adaptador
Google Ads real foi iniciado. Nenhuma credencial real foi criada, lida ou registrada.

## Developer Token — reclassificação (não remoção da exigência)

`CHECKLIST_CADASTROS_PLATAFORMAS_20260827.md` §1 descrevia a obtenção do developer token
como se fosse, por si só, a arquitetura de autenticação do canal Google Ads. **Isso é
impreciso e foi corrigido** (ver Adendo naquele arquivo): o developer token continua
sendo exigido pela Google Ads API (é um header obrigatório em toda chamada, ao lado do
access token OAuth) — **não removido como requisito técnico**. O que muda é o
enquadramento: o developer token é **uma credencial PLATFORM entre várias** (ao lado do
OAuth Client Web e do redirect URI), nunca o mecanismo completo de autenticação
multi-tenant. Quem autentica CADA cliente é o fluxo OAuth por tenant (itens 1-5 acima);
o developer token só prova, à Google, qual aplicativo (CampaIA) está fazendo a chamada —
o mesmo racional já formalizado na tabela "Duas camadas de credencial" da ADR-0013
original (25/08/2026).

## Status

`DOCUMENTAL`. Nenhum merge, deploy, alteração de produção ou início de adaptador Google
Ads ocorreu nesta tarefa. Ver adendos correspondentes em `09_ADR_0013_CREDENCIAIS_E_CONFIGURABILIDADE.md`
e em `CHECKLIST_CADASTROS_PLATAFORMAS_20260827.md`.
