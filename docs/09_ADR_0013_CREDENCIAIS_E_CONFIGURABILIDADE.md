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
