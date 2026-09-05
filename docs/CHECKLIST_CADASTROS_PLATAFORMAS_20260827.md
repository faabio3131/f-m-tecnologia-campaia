# CAMPAIA — CHECKLIST: CADASTRO DE DESENVOLVEDOR (GOOGLE ADS, META, WHATSAPP)

**Criado em:** 27 de agosto de 2026
**Fonte:** consulta direta à documentação oficial de cada plataforma em 27/08/2026 (Google Ads API docs, Meta for Developers docs, WhatsApp Cloud API docs)
**Contexto:** decorre da priorização do Diretor em 27/08/2026 de destravar dependências externas com prazo de aprovação de terceiros, identificadas como "caminho crítico" em `04_DECISOES_DO_DIRETOR.md`. O CNPJ da F&M Tecnologia já está em processo de abertura por fora (contabilidade do Diretor) — este checklist não depende disso para começar, exceto onde indicado.

**Natureza deste documento:** é um guia de execução, não uma decisão a ser tomada. Os passos abaixo exigem ação direta do Diretor (ou de quem ele designar) em contas comerciais reais — Claude não tem acesso a essas plataformas e não pode executar nenhum destes passos.

---

## ORDEM RECOMENDADA E POR QUÊ

Seguindo a ordem de canais já aprovada (D-04/ADR-0007: Google → Meta → conjunto → WhatsApp), mas com uma diferença importante: **os CADASTROS podem e devem começar em paralelo desde já**, mesmo que o USO técnico dos canais siga a ordem sequencial. Isso porque os prazos de aprovação de terceiros não têm relação com a ordem de integração técnica — quanto mais cedo abrir, menos tempo de espera consome o cronograma depois.

**Atenção especial:** o cadastro do WhatsApp cria automaticamente uma Meta Business Account, se ainda não existir — então iniciar pela Meta primeiro é o caminho mais eficiente, mesmo que o USO do WhatsApp em produção só venha na etapa 4.

---

## 1. GOOGLE ADS — TOKEN DE DESENVOLVEDOR

**Fonte:** developers.google.com/google-ads/api/docs/get-started/dev-token

- [ ] **Pré-requisito:** ter uma conta Google Ads de **gerenciador (manager account)** — não é a mesma coisa que uma conta de anúncio comum. Se não existir, precisa ser criada primeiro com um e-mail que nunca tenha sido vinculado antes a nenhuma conta Google Ads.
- [ ] Acessar o **API Center**: ads.google.com/aw/apicenter, logado na conta de gerenciador.
- [ ] Preencher o formulário de acesso à API com: nome da empresa (F&M Tecnologia) e URL do site funcionando; e-mail de contato monitorado com frequência (a Google pode entrar em contato durante a revisão).
- [ ] Aceitar os Termos e Condições.
- [ ] **Resultado inicial:** o token começa em nível **"Test Account Access"** (só funciona contra contas de teste, não contas reais).
- [ ] **Passo seguinte (mais tarde):** solicitar elevação para **"Basic Access"** ou **"Standard Access"** — isso exige revisão adicional da Google e não tem prazo garantido.

**Bloqueio identificado:** exige site funcionando da empresa — se o domínio/site do CAMPAIA ainda não existir publicamente, isso pode atrasar a aprovação. Verificar antes de submeter.

---

## 2. META (FACEBOOK + INSTAGRAM) — APP E BUSINESS VERIFICATION

**Fonte:** developers.facebook.com/docs/development/release/

- [ ] Criar uma **Meta Business Account** (Business Manager), se ainda não existir.
- [ ] Criar um **App** no Meta for Developers (developers.facebook.com), associado a essa Business Account.
- [ ] Identificar exatamente quais permissões/recursos o CAMPAIA vai precisar (ex.: `ads_management`, `pages_read_engagement`, etc.) — isso será formalizado quando a integração técnica da etapa Meta for desenhada.
- [ ] Submeter o app para **App Review**, descrevendo por que cada permissão é necessária e demonstrando como os dados retornados são usados. **Obrigatório** sempre que o app for usado por pessoas sem papel administrativo dentro dele (ou seja, por qualquer cliente real do CAMPAIA).
- [ ] Completar a **Business Verification** — obrigatória para: (a) permissões de acesso avançado, e (b) qualquer app que permita que outras empresas (os clientes do CAMPAIA) acessem os próprios dados delas através do app. **Sem isso, usuários de outras organizações não conseguem conceder permissão ao app.**
- [ ] **Somente depois** de todas as permissões necessárias estarem aprovadas E a Business Verification completa: mudar o app de modo "Development" para modo **"Live"**.

**Aviso oficial retirado da documentação, importante:** *"Se você mudar seu app para o modo Live prematuramente, seu app ficará impossibilitado de solicitar permissão não aprovada de usuários do app."* — ou seja, não adianta apressar essa troca antes das aprovações estarem prontas.

**Bloqueio identificado:** a Business Verification pode exigir documentos formais da empresa (possivelmente incluindo CNPJ) — item a confirmar assim que o CNPJ da F&M Tecnologia estiver emitido.

---

## 3. WHATSAPP BUSINESS PLATFORM (CLOUD API)

**Fonte:** developers.facebook.com/docs/whatsapp/cloud-api/get-started

- [ ] Criar o produto WhatsApp dentro da mesma Meta Business Account do item 2 (o processo cria automaticamente uma WhatsApp Business Account de teste, se ainda não existir).
- [ ] Um número de telefone comercial de teste e um conjunto de templates de mensagem pré-aprovados são gerados automaticamente nesta fase inicial — **não é necessário esperar aprovação de template para começar a testar**.
- [ ] Cadastrar até 5 números de destinatário para teste — cada um recebe um código de confirmação via WhatsApp para validação.
- [ ] Enviar mensagens de teste usando os templates pré-aprovados, pelo painel de configuração da API.
- [ ] Configurar webhooks (URL de callback) para receber notificações em tempo real de entrega, leitura e respostas — isso depende de o backend já ter um endpoint pronto para receber, o que só faz sentido próximo da Fase 7 real.
- [ ] **Só quando for para produção real** (não teste): adicionar um número de telefone comercial real e criar uma WhatsApp Business Account real para atendimento a clientes de verdade.

**Restrição já registrada em ADR-0007:** este item, tecnicamente, só é utilizável em produção depois que a etapa Meta (item 2) estiver madura — mas o **cadastro** em si (Meta Business Account, App) pode e deve ser feito junto com o item 2, já que ambos compartilham a mesma conta.

---

## RESUMO — O QUE PODE COMEÇAR JÁ, HOJE

| Ação | Depende de algo pendente? |
|---|---|
| Criar Google Ads manager account + submeter formulário de developer token | Não — pode começar já. Atenção ao requisito de site funcionando. |
| Criar Meta Business Account + App | Não — pode começar já. |
| Submeter App Review da Meta | Depende de já ter decidido quais permissões o app vai pedir (desenho técnico da integração Meta) |
| Completar Business Verification da Meta | Pode precisar de CNPJ da F&M Tecnologia — confirmar assim que emitido |
| Cadastro de teste do WhatsApp (Cloud API) | Não — pode começar assim que a Meta Business Account existir, mesmo em modo de teste |
| WhatsApp em produção real (número comercial real) | Depende da etapa Meta estar madura (restrição técnica de ADR-0007) e de CNPJ/LGPD resolvidos (D-09) |

**Nenhum destes itens foi executado nesta sessão** — são ações que exigem acesso direto do Diretor (ou de quem ele designar) a contas comerciais reais, fora do alcance de Claude.
