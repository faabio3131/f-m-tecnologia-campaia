# CampaIA — Cronograma Mestre de Finalização (backend → web → produção)

**Data:** 24/09/2026 · **Base:** estado real confirmado nesta data — `01_PAINEL_EXECUCAO_v20_VIGENTE.md`,
ADRs 0016–0020, e o trabalho de reconciliação/billing/Asaas concluído hoje (24/09).

**Regra deste documento:** cada item aqui é `FATO CONFIRMADO` (já decidido/construído),
`DECISÃO PENDENTE` (precisa de você) ou `TARGET` (a construir). Nenhum item vira `CONCLUÍDO`
sem evidência real — mesma disciplina do resto do projeto. Este cronograma organiza o backlog
em **3 etapas sequenciais**, cada uma com seu próprio prompt de execução (seção final).

---

## Onde estamos agora (FATO CONFIRMADO, 24/09/2026)

| Área | Estado |
|---|---|
| Núcleo de domínio (`campaia_core/`) | 338 testes, 100% verdes |
| Camada HTTP (`api/`) | 97 testes, 100% verdes — inclui billing/Asaas agora |
| Motor de cobrança própria (assinatura + créditos extras) | Construído, testado, integrado à API |
| Gateway Asaas | Verificado contra Sandbox real; produção pendente de CNPJ da F&M |
| Webhook de confirmação de pagamento | Construído, testado, integrado; dedupe ainda em memória |
| Catálogo de preços dos planos | Configurável por arquivo externo; valores reais ainda não definidos |
| Autenticação da API | Tokens fixos de desenvolvimento — **nunca foi login real** |
| System Design Web (ADR-0016–0019) | **APROVADO** (19/09): Next.js/React, auth via OAuth/OIDC gerenciado + sessão server-side, deploy em containers no Google Cloud (`southamerica-east1`) |
| Frontend Web | **Zero linhas implementadas** — só o desenho aprovado |
| App mobile (Flutter) | Em quarentena arquitetural desde 19/09, sem evolução |
| Conectores reais (Google Ads, Meta, WhatsApp) | Só simulados — Fases 5, 6 e 7 do painel, **NÃO INICIADAS** |
| Analytics/Insights reais | Fase 9, **NÃO INICIADA** (`GET /insights` devolve lista vazia, honestamente) |
| Infraestrutura de nuvem real | D-08/ADR-0019 aprovam Google Cloud/São Paulo; **nada provisionado ainda** |
| Segurança e robustez formais | Fase 10, **NÃO INICIADA** (só as fm-security-review pontuais de hoje) |
| Homologação | Fase 11, **NÃO INICIADA** |
| Produção/comercialização | Fase 12 — exige sua autorização expressa, específica, no momento |

---

## ETAPA 1 — Fechar e endurecer o backend (fundação antes de qualquer interface)

**Por quê primeiro:** nada do resto (web, mobile, conectores reais) deve ser construído sobre
uma fundação com autenticação falsa e achados de segurança em aberto. Esta etapa não depende
de nenhuma decisão de produto nova — só de você prover 2 insumos (preços, credencial Asaas de
produção quando o CNPJ sair).

| # | Item | Tipo | Pendência |
|---|---|---|---|
| 1.1 | Dedupe do webhook do Asaas persistido (não só em memória) | TARGET | Nenhuma — engenharia pura |
| 1.2 | Rate limiting no endpoint público `/webhooks/asaas` | TARGET | Nenhuma |
| 1.3 | Autenticação real da API (hoje é token fixo de dev) — substituir por sessão real, alinhado ao provedor OAuth/OIDC já aprovado na ADR-0018 para o Web | TARGET | Decisão: qual provedor de identidade gerenciado (ex.: Auth0, Google Identity Platform, Clerk) — ADR-0018 aprovou o *padrão*, não o provedor específico |
| 1.4 | Gestão de segredos real (Secret Manager do Google Cloud, já na direção de D-08/ADR-0019) — hoje tudo é variável de ambiente solta | TARGET | Nenhuma, depende só da infraestrutura provisionada (1.6) |
| 1.5 | Tabela real de preços dos planos | DECISÃO PENDENTE | Você define valores (franquia, créditos incluídos, preço do crédito extra) |
| 1.6 | Provisionamento real da infraestrutura (Cloud SQL, Secret Manager, Pub/Sub — D-08/ADR-0019) | TARGET | Autorização para contratar/configurar nuvem (ainda não dada — ADR-0019 diz "não contratar nesta missão") |
| 1.7 | Conta Asaas de produção + troca de `ASAAS_MODE=SANDBOX` para `PRODUCTION` | DECISÃO PENDENTE | CNPJ da F&M (em andamento com sua contabilidade) |
| 1.8 | `fm-certify-change` formal sobre todo o backend, HEAD único | TARGET | Nenhuma |
| 1.9 | `fm-security-review` formal de ponta a ponta (não só nos módulos de billing) | TARGET | Nenhuma |

**Critério de saída da Etapa 1:** backend com autenticação real, segredos geridos, 100% dos
achados de segurança conhecidos corrigidos ou formalmente aceitos, `fm-certify-change` com
veredito `CERTIFICADO` (não "com pendências").

---

## ETAPA 2 — Construir a aplicação Web (o design já está aprovado)

**Por quê depois:** as ADRs 0016–0019 já resolveram framework, autenticação e deploy — esta
etapa é implementação sobre uma decisão já tomada, não desenho novo. Depende da Etapa 1 porque
a autenticação Web (ADR-0018) precisa do backend já falando OAuth/OIDC de verdade.

| # | Item | Tipo | Pendência |
|---|---|---|---|
| 2.1 | Scaffold do frontend Next.js/React (WP-01) | TARGET | Prompt Mestre de implementação Web dedicado — o painel v20 é explícito: "não iniciar antes desse prompt" |
| 2.2 | Autenticação de sessão Web (cookies `HttpOnly`/`Secure`/`SameSite`, CSRF) — ADR-0018 | TARGET | Depende de 1.3 (provedor de identidade escolhido) |
| 2.3 | Implementar as 20 telas já especificadas (`docs/product/13_ESPECIFICACAO_TELAS_APP.md`) | TARGET | Nenhuma nova — especificação já existe e é mais completa que a versão feita erroneamente em 23/09 |
| 2.4 | Resolver as 4 pendências de produto que a especificação de telas já registrou (login real, edição de Brand Kit, escopo de objetivos do briefing, superfície de UI da assinatura) | DECISÃO PENDENTE | Suas respostas a cada uma |
| 2.5 | Decisão final sobre o app mobile (sair da quarentena, descartar, ou retomar depois do Web) | DECISÃO PENDENTE | Sua confirmação — `docs/evidence/MOBILE_QUARENTENA_ARQUITETURAL_20260919.md` |
| 2.6 | Deploy do frontend + BFF como containers no Google Cloud (ADR-0019) | TARGET | Depende de 1.6 (infraestrutura provisionada) |
| 2.7 | Testes E2E do fluxo completo (briefing → aprovação → publicação → métricas → pausa) contra conectores simulados | TARGET | Nenhuma |

**Critério de saída da Etapa 2:** um usuário real consegue logar, criar um briefing, ver o
plano gerado, aprovar, "publicar" (em simulador) e ver o estado refletido na tela — de ponta a
ponta, na Web, não só via `curl`.

---

## ETAPA 3 — Integrações reais externas, homologação e produção

**Por quê por último:** exige contas reais em plataformas de terceiros (Google Ads, Meta,
WhatsApp), cada uma com processo de aprovação próprio e fora do seu controle direto — não faz
sentido correr atrás disso antes de a Web e o backend estarem prontos para receber tráfego real.

| # | Item | Tipo | Pendência |
|---|---|---|---|
| 3.1 | Google Ads: developer token real (Fase 5) | TARGET | Conta já criada (Google Ads Manager, 27/08); falta solicitar Basic Access (~5 dias úteis) |
| 3.2 | Meta: App Review + Business verification + Marketing API Access Tier (Fase 6) | TARGET | Conta Meta Business Manager já criada (27/08); processo de revisão da Meta, fora do seu controle direto |
| 3.3 | WhatsApp Business: conta real, número, templates aprovados (Fase 7) | TARGET | Pendia de D-09 (CNPJ da F&M) — mesma pendência da Etapa 1 |
| 3.4 | Substituir os 3 simuladores por conectores reais, um por vez, na ordem já decidida (D-04: Google → Meta → conjunto → WhatsApp) | TARGET | Depende de 3.1–3.3 |
| 3.5 | Analytics/Insights reais (Fase 9) — ingestão real de métricas dos conectores acima | TARGET | Depende de 3.4 |
| 3.6 | Segurança e robustez formais (Fase 10) — pentest, hardening final, revisão de dependências | TARGET | Nenhuma, mas fica mais barato depois da Etapa 1 já ter fechado os achados conhecidos |
| 3.7 | Homologação completa (Fase 11) — matriz de validação de ponta a ponta, QA formal | TARGET | Nenhuma |
| 3.8 | Autorização expressa e específica para produção (Fase 12) | DECISÃO PENDENTE | Sua autorização final, no momento — nunca presumida |

**Critério de saída da Etapa 3:** CampaIA rodando em produção real, com pelo menos um canal
publicitário real conectado, homologado, e comercialmente disponível — os 3 últimos estados da
escala do projeto (`HOMOLOGADO` → `PRONTO PARA PRODUÇÃO` → `COMERCIALMENTE DISPONÍVEL`).

---

## Os 3 prompts de execução

Cada prompt abaixo é autocontido — pode ser colado numa sessão nova, em qualquer ordem que
você escolher rodar (embora a ordem 1 → 2 → 3 seja a recomendada, pelas dependências acima).
Cada um instrui a sessão a **reconstruir o estado real antes de agir** (mesma disciplina de
sempre), não presumir nada deste documento como ainda válido sem checar.

### Prompt 1 — Fechar e endurecer o backend

```
Estamos na Etapa 1 do cronograma mestre (docs/19_CRONOGRAMA_MESTRE_FINALIZACAO.md) do
repositório canônico faabio3131/f-m-tecnologia-campaia. Antes de qualquer coisa, leia
CLAUDE.md, os dois documentos mestres da Nova FM (docs/nova-fm/), e o próprio cronograma —
depois reconstrua o estado real do repositório (branch, HEAD, suíte de testes) por execução
direta, nunca por suposição ou por confiar neste texto sozinho.

Objetivo desta etapa: fechar os achados de segurança e produção que ainda estão em aberto no
motor de cobrança/Asaas, e substituir a autenticação de desenvolvimento por autenticação real.

Trabalhe os itens 1.1 a 1.9 do cronograma, nesta ordem de prioridade técnica (não a ordem da
tabela): primeiro os achados de segurança que já têm solução conhecida e não dependem de mim
(1.1 dedupe persistido do webhook, 1.2 rate limiting, 1.8 fm-certify-change, 1.9
fm-security-review completo) — construa, teste e documente cada um com evidência real, exatamente
como já foi feito nos blocos de hoje (ADR quando houver decisão de arquitetura, documento de
evidência, testes que provem o achado antes de corrigi-lo).

Para os itens que dependem de mim (1.3 provedor de identidade, 1.5 preços dos planos, 1.6
autorização para provisionar nuvem, 1.7 conta Asaas de produção): pare e pergunte, com uma
recomendação clara marcada, antes de escolher por conta própria — não presuma.

Ao final, rode fm-certify-change formal sobre o HEAD final e me diga o veredito exato.
```

### Prompt 2 — Construir a aplicação Web

```
Estamos na Etapa 2 do cronograma mestre (docs/19_CRONOGRAMA_MESTRE_FINALIZACAO.md) do
repositório canônico faabio3131/f-m-tecnologia-campaia. Antes de qualquer coisa, leia
CLAUDE.md, os documentos mestres da Nova FM, as ADRs 0016 a 0020, a especificação de telas em
docs/product/13_ESPECIFICACAO_TELAS_APP.md, e o próprio cronograma — depois confirme por
execução real (não suposição) se a Etapa 1 (backend endurecido, autenticação real) já foi
concluída. Se não foi, pare e me avise antes de prosseguir — esta etapa depende dela.

Objetivo: implementar o frontend Web (Next.js/React, conforme ADR-0017) sobre o desenho já
aprovado (ADR-0016 a 0019), começando pelo scaffold (WP-01) e avançando pelas 20 telas já
especificadas.

Antes de escrever qualquer linha de frontend, resolva comigo as 4 pendências de produto que a
especificação de telas já registrou (item 2.4 do cronograma) — apresente cada uma com uma
recomendação clara marcada, não decida sozinho. Também confirme comigo a decisão sobre o app
mobile (item 2.5) antes de tocar em qualquer coisa relacionada a ele.

Construa de forma incremental, testável a cada etapa (nunca uma tela sem endpoint real por
trás — mesma disciplina já usada na especificação). Ao final, rode o fluxo completo end-to-end
(briefing → aprovação → publicação simulada → métricas → pausa) manualmente no navegador e me
mostre que funciona de verdade, não só que os testes automatizados passam.
```

### Prompt 3 — Integrações reais, homologação e produção

```
Estamos na Etapa 3 do cronograma mestre (docs/19_CRONOGRAMA_MESTRE_FINALIZACAO.md) do
repositório canônico faabio3131/f-m-tecnologia-campaia — a etapa final antes de produção.
Antes de qualquer coisa, leia CLAUDE.md, os documentos mestres da Nova FM, o painel de
execução vigente e o próprio cronograma — depois confirme por execução real se as Etapas 1 e 2
já foram concluídas. Se não foram, pare e me avise antes de prosseguir.

Objetivo: substituir os conectores simulados (Google Ads, Meta, WhatsApp) pelos reais, na
ordem já decidida (D-04: Google → Meta → conjunto → WhatsApp), ligar analytics real, fechar
segurança/robustez e homologação, e preparar (nunca executar sozinho) a autorização de
produção.

Cada conector real depende de uma conta/credencial que só eu posso prover — pergunte antes de
presumir que uma conta existe ou que uma aprovação de plataforma (Meta App Review, WhatsApp
Business) já saiu. Trabalhe um conector por vez, até o Gate de Integração (G4) de cada um,
antes de passar para o próximo.

Segurança e robustez (item 3.6) e homologação (item 3.7) devem rodar depois de pelo menos um
conector real estar de pé, contra o sistema real, não só contra simuladores.

NUNCA declare produção pronta ou autorizada por conta própria. O item 3.8 (autorização de
produção) exige minha confirmação explícita, específica e no momento — apresente o que está
pronto, com evidência, e espere minha decisão.
```

---

## Observação final

Este cronograma cobre o que já se sabe hoje que falta. Coisas que ainda não foram descobertas
(um novo achado de segurança, uma mudança de política de uma plataforma, uma decisão sua que
muda escopo) vão aparecer no caminho — a disciplina deste projeto é registrar isso quando
acontecer, não fingir que o plano original ainda vale sem reconciliar.
