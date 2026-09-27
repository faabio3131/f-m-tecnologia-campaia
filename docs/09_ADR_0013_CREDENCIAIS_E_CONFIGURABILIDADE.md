# ADR-0013 — Modelo de credenciais e limites da configurabilidade

**Status:** PROPOSTA · **Data:** 25/08/2026 · **Aprovador:** Fábio Aluizio da Silva

## Contexto

Decisão do Diretor em 25/08/2026:

> O aplicativo deve ser 100% configurável. Quem contratar terá abas e locais para configurar cada conta —
> Google, Meta, WhatsApp, Facebook, Instagram — preencher e colocar para rodar. Depois de pronto, testamos
> com as contas do Diretor, validamos o produto e então comercializamos.

Essa decisão está correta e **desbloqueia o desenvolvimento**: nada impede construir o produto inteiro
enquanto as autorizações externas correm em paralelo.

Mas ela exige uma distinção que muda o desenho, e que precisa ficar explícita antes do código.

## Duas camadas de credencial que não são a mesma coisa

| Camada | De quem é | Configurável pelo cliente? |
|---|---|---|
| **Conta do cliente** — conta de anúncios Google, ad account da Meta, Página, Instagram, número do WhatsApp | Do cliente | **Sim.** É exatamente o que as abas de configuração fazem, por OAuth |
| **Credencial de plataforma** — developer token do Google Ads, App da Meta e suas permissões aprovadas, app do WhatsApp | **Nossa (CAMPAIA)** | **Não.** O cliente não tem como fornecer isso |

O cliente conecta a conta dele. Mas quem executa a chamada à API é o nosso app, com a nossa credencial de
plataforma. É por isso que as aprovações externas existem: as plataformas querem saber quem é o software que
vai operar contas de terceiros.

**Consequência prática:** a aba de configuração funciona 100% desde o primeiro dia — em simulador, em conta de
teste e nas contas do Diretor. O que as aprovações externas liberam não é a configuração; é operar contas de
**outros clientes** em produção.

**Isso não atrasa nada da construção.** Atrasa apenas o último passo, a comercialização — que é exatamente
onde o Diretor já colocou esse passo.

## Por que testar com as contas do Diretor é a jogada certa

Operar contas dentro do nosso próprio Business Manager é o cenário que **não** exige App Review. E o tier da
Marketing API da Meta exige histórico real de chamadas com taxa de erro baixa. Ou seja:

> Testar com as contas do Diretor não é só validação de produto. É o que **gera a evidência** que as
> plataformas pedem para liberar produção com contas de terceiros.

O caminho vira: simulador → conta de teste → contas do Diretor (valida o produto **e** constrói o histórico
de aprovação) → comercial.

## Decisão

**1. Dois modos de credencial, desde o desenho:**

| Modo | Como funciona | Para quem |
|---|---|---|
| **PLATFORM** (padrão comercial) | Cliente conecta a conta dele por OAuth; a CAMPAIA opera com a credencial de plataforma | Cliente comum |
| **BYO** (traga a sua) | Cliente fornece o próprio developer token, o próprio App da Meta ou a própria WABA | Agência, cliente grande, ou o próprio Diretor na fase de validação |

O modo é configuração por `external_account`, não decisão global. O adaptador não sabe a diferença: resolve a
credencial pelo `external_account_id` contra o cofre, como já previsto no contrato do Connector Hub.

**2. O que é configurável pelo cliente:** contas e conexões; Brand Kit; objetivo; orçamento e limites;
canais; nível de autonomia (dentro do teto do plano); provedor e modelo de IA; janelas de horário; palavras,
alegações e públicos vetados; notificações; usuários e papéis.

**3. O que NÃO é configurável — trava de produto, não preferência:**

- desligar o Policy Engine, o Budget Engine ou a trilha de auditoria;
- publicar sem aprovação humana nos gatilhos obrigatórios;
- remover o kill switch;
- conceder credencial de anúncios à IA;
- desativar isolamento entre tenants;
- elevar autonomia acima do teto contratado;
- ignorar consentimento e opt-out do WhatsApp.

Configurável significa *ajustável dentro de limites*, não *desativável*. Se o cliente pudesse desligar a
trava de orçamento, o primeiro defeito de software viraria prejuízo dele e processo nosso.

**4. Provider Simulator obrigatório.** Um adaptador que implementa o mesmo contrato do Connector Hub e
devolve respostas realistas, incluindo falhas: `RATE_LIMITED`, `PARTIAL_FAILURE`, `AUTH_EXPIRED`,
`CAPABILITY_UNSUPPORTED`. Todo o produto é construído e testado contra ele. Trocar simulador por adaptador
real é configuração, não reescrita.

## Consequências

Fica mais fácil: o desenvolvimento anda sem depender de aprovação externa; o teste de falha fica melhor no
simulador do que na plataforma real, porque conseguimos provocar o erro de propósito.

Fica mais difícil: manter o simulador fiel exige disciplina. Simulador que só devolve sucesso é armadilha —
por isso ele nasce com catálogo de falhas obrigatório.

A revisitar: quando o primeiro adaptador real entrar em sandbox, comparar respostas com o simulador e
corrigir as divergências.

## Riscos

| Risco | Mitigação |
|---|---|
| Simulador criar falsa sensação de "pronto" | Gate de Integração exige sandbox real; mock não comprova integração (Ordem Mestra, item 14) |
| Modo BYO expor o cliente a configuração incorreta | Validação de credencial na conexão + capability probe antes de habilitar ações |
| Cliente esperar publicar em produção antes das aprovações | A interface informa o estado real da conta: SIMULADOR / TESTE / PRODUÇÃO. Nunca simular sucesso |

---

## Adendo (27/09/2026) — Cofre construído; reafirmação e correção de rumo

**Contexto do adendo:** durante a Fase 5-7 do desenvolvimento (integrações reais), o
trabalho começou a se desviar para configurar credenciais de teste (conta Google Ads
sandbox do Diretor/Nova FM) como se fossem a arquitetura comercial — variáveis de
ambiente globais para `GOOGLE_ADS_CUSTOMER_ID`/`GOOGLE_ADS_LOGIN_CUSTOMER_ID`/refresh
token. O Diretor corrigiu isso explicitamente: *"Eu não posso mexer no código só para
configurar o cliente... o software tem que ser construído na base multi-tenant,
configurável."* Esta ADR já previa essa distinção desde 25/08/2026 (tabela "Duas
camadas de credencial"); o que faltava era o cofre em si.

**Construído em 27/09/2026** (`campaia_core/credential_vault.py`, `api/repositories.py::VaultRepository`):

- `CredentialCipher` — criptografia real (Fernet/AES), chave de `CAMPAIA_VAULT_KEY`,
  fail-closed sem ela (nunca uma chave padrão).
- `VaultRepository` — armazenamento por tenant (SQLite quando persistente), isolamento
  cross-tenant garantido por construção (`resolve()` recusa um `SecretRef` de outro
  tenant, mesmo com a chave certa).
- `Connection.secret_ref` — a única coisa que um registro de conexão guarda sobre o
  segredo; nunca o valor em claro.
- `oauth_callback`/`revoke_connection` já gravam/revogam no cofre de verdade quando um
  token real é fornecido.

**Reafirmado, com data e proveniência:**

1. Nenhuma integração comercial do CampaIA pode exigir intervenção manual do
   desenvolvedor para provisionar um novo tenant. Toda configuração específica do
   cliente é feita pelo próprio produto, por um usuário autorizado daquele tenant.
2. Credenciais de **PLATFORM** (Client ID/Secret do app CampaIA perante cada provedor —
   Google, Meta, WhatsApp) permanecem centralizadas por ambiente, nunca por tenant.
3. Segredos de **TENANT** (token de cada cliente) ficam exclusivamente no Credential
   Vault; todo outro objeto de domínio guarda só a `SecretRef` opaca.
4. Uma integração testada com a conta do Diretor (sandbox Google Ads, 26-27/09/2026) é
   evidência de engenharia/homologação — nunca a arquitetura de provisionamento dos
   clientes reais.
5. **Gateway de pagamento** segue a mesma régua da tabela de credenciais acima, pela
   pergunta "para quem esse gateway está movimentando dinheiro?": o Asaas usado para
   cobrar a assinatura do CampaIA (ADR-0020) é **PLATFORM**; um gateway que um tenant
   conectasse no futuro para cobrar os próprios clientes seria **TENANT**.

**TARGET ainda pendente, registrado como `EXTERNAL_INFRASTRUCTURE` (não fabricado como
concluído):** a troca real de OAuth server-side — usuário do tenant → CampaIA →
Google/Meta OAuth Consent Screen → `authorization_code` + `state` → callback do backend
CampaIA → troca do código por tokens diretamente com o provedor → gravação direta no
Vault → `Connection` recebe só a `SecretRef` → **o refresh token nunca trafega pelo
browser**. Depende de um Client OAuth tipo "Aplicativo da Web" com domínio de callback
publicado, que não existe ainda (a Web da Nova FM não está em produção).

**Status desta ADR:** permanece `PROPOSTA` quanto ao modelo de dois modos
(PLATFORM/BYO), mas a camada de armazenamento (cofre) que a viabiliza tecnicamente
passa de `PREVISTA` para `IMPLEMENTADA E TESTADA` nesta data.

---

## Adendo (27/09/2026, parte 2) — correção: campo `credential` retirado do contrato público; arquitetura-alvo Google Ads

**Correção sobre o adendo anterior (mesma data, acima):** a frase *"o campo `credential`
aceito hoje por `POST /connections/oauth/callback` é um mecanismo de bootstrap/teste"*
ficou **desatualizada horas depois de escrita**, pela Auditoria Independente #3
(27/09/2026, achado 4): esse campo foi **retirado por completo** do contrato público
(`contracts/bff-openapi.yaml`) — `OAuthCallbackRequest` agora rejeita com 422
(`extra_forbidden`) qualquer tentativa de envio. A testabilidade do Vault foi preservada
por uma rota dev/test-only, deliberadamente fora do contrato público:
`POST /connections/{connectionId}/dev-attach-credential` (fail-closed fora de
test/dev-local). Este parágrafo substitui a descrição anterior — **CURRENT real, não
histórico**, confirmado por leitura de `backend/api/models.py` e
`backend/api/routes_connections.py` nesta data.

**Arquitetura-alvo para o canal Google Ads especificamente** (detalhada em
`docs/evidence/EVIDENCIA_GOOGLE_ADS_ARQUITETURA_OAUTH_MULTITENANT_20260927.md`, que este
parágrafo resume e que prevalece em caso de divergência futura):

1. **OAuth Client tipo "Web Application"** e a **Redirect URI oficial do CampaIA** são
   credenciais **PLATFORM** (mesma linha de raciocínio da tabela acima) — distintas do
   OAuth Desktop Client já existente, que fica reservado exclusivamente a teste/uso
   manual, nunca a fluxo comercial (um Desktop Client não suporta redirect server-side
   com domínio de callback).
2. **Multi-tenant real, sem MCC obrigatório:** cada tenant autoriza a própria conta
   Google Ads via OAuth. Uma conta gerenciadora (MCC) da própria Nova FM, quando
   existir, serve só para homologação/administração interna — nunca um vínculo que todo
   cliente precise ter.
3. **Customer ID por conexão, nunca por variável de ambiente global** — reafirma a
   correção já registrada no adendo anterior (`GOOGLE_ADS_CUSTOMER_ID`/
   `GOOGLE_ADS_LOGIN_CUSTOMER_ID` como env var global foi um desvio já corrigido pelo
   Diretor; confirmado por grep real em 27/09/2026 que esses env vars não existem no
   código).
4. **Developer token reclassificado, não removido como exigência:** continua sendo um
   header obrigatório de toda chamada à Google Ads API (credencial **PLATFORM**), mas
   não é — e nunca foi, segundo esta ADR desde 25/08/2026 — o mecanismo completo de
   autenticação por tenant. Quem autentica cada cliente é o fluxo OAuth (itens 1-2).

**Nada dos itens 1-4 foi implementado nesta tarefa** (puramente documental). Nenhum
OAuth Client Web foi criado (ação de Google Cloud Console, fora do alcance de Claude).
Nenhum adaptador Google Ads real foi iniciado.
