# NOVA FM TECNOLOGIA
# DOCUMENTO MESTRE DE FUNDAÇÃO
## CONSTITUIÇÃO DE PRODUTO, ARQUITETURA, ENGENHARIA E OPERAÇÃO

**Status:** NORMA MESTRE OBRIGATÓRIA  
**Versão:** 2.0  
**Fundação original:** 13/09/2026  
**Revisão e consolidação:** 17/09/2026  
**Aplicabilidade:** todos os produtos, SaaS, softwares, sistemas, plataformas, sites, serviços, APIs, módulos, automações e soluções de inteligência artificial construídos pela Nova FM Tecnologia.

---

# 1. PROPÓSITO

Este Documento Mestre estabelece a fundação institucional obrigatória para pesquisa, concepção, arquitetura, desenvolvimento, segurança, testes, homologação, operação, documentação, evolução e comercialização dos produtos da Nova FM Tecnologia.

Seu objetivo é impedir:

- retrabalho estrutural;
- reconstruções previsíveis;
- arquiteturas paralelas;
- migrações evitáveis;
- duplicação de regras;
- duplicação de autoridades;
- desenvolvimento estrutural sem compreensão suficiente do problema;
- desenvolvimento comercial sem validação de mercado quando aplicável;
- decisões arquiteturais baseadas apenas em preferência;
- código provisório transformado silenciosamente em produção;
- crescimento desordenado da base de código;
- perda de contexto;
- perda de rastreabilidade;
- dependência desnecessária de fornecedores;
- vulnerabilidades previsíveis chegando ao cliente;
- funcionalidades declaradas prontas sem evidência;
- inteligência artificial assumindo autoridades pertencentes a sistemas determinísticos.

A Nova FM Tecnologia deve transformar cada hora de engenharia em valor acumulativo e reutilizável.

A filosofia central é:

**CONSTRUIR UMA VEZ, NA ESTRUTURA CERTA, E EVOLUIR CONTINUAMENTE.**

Tempo humano, tempo de engenharia e capital são recursos finitos.

Produto, arquitetura e engenharia devem preservá-los.

---

# 2. AUTORIDADE DESTE DOCUMENTO

Este Documento Mestre é a norma horizontal de produto e engenharia da Nova FM Tecnologia.

Documentos específicos de cada projeto podem complementar esta norma por meio de:

- Documento Mestre do Produto;
- pesquisa Product & Market;
- requisitos de produto;
- Plano Mestre;
- System Design;
- Arquitetura Mestre;
- Architecture Decision Records — ADRs;
- contratos de API;
- schemas;
- especificações de segurança;
- planos de testes;
- runbooks;
- documentação operacional;
- changelogs;
- documentação de releases.

Esses documentos não devem contradizer esta fundação silenciosamente.

Quando uma necessidade real exigir exceção, ela deve ser:

1. identificada;
2. justificada;
3. analisada quanto ao impacto;
4. registrada;
5. aprovada pela autoridade competente;
6. documentada.

Conveniência de curto prazo, isoladamente, não constitui justificativa arquitetural.

---

# 3. PRINCÍPIO FUNDAMENTAL — ARQUITETURA ÚNICA EVOLUTIVA

Todo produto da Nova FM Tecnologia deve possuir uma única linha arquitetural evolutiva.

Não deve existir como estratégia normal:

V1 técnica  
→ migração tecnológica  
→ V1 comercial  
→ reconstrução  
→ nova arquitetura.

O padrão institucional é:

V1 na arquitetura comercial pretendida  
→ V1.1  
→ V1.2  
→ V2  
→ evolução incremental e controlada.

A primeira versão pode ser pequena.

Ela não deve ser estruturalmente descartável quando já existe intenção de transformá-la em produto comercial.

O objetivo não é antecipar toda a complexidade ou escala futura.

O objetivo é evitar decisões que tornem previsível uma reconstrução posterior.

---

# 4. REGRA DE OURO — UMA ÚNICA LINHA DE PRODUTO

Desenvolvimento, homologação e produção devem representar ambientes diferentes da mesma aplicação e da mesma arquitetura, e não produtos tecnologicamente diferentes.

Backend, Web, APIs, autenticação, autorização, tenant, dados, migrations, segurança, testes, observabilidade, infraestrutura e deploy devem fazer parte do desenho inicial quando necessários à operação comercial.

A interface pode evoluir.

A infraestrutura pode escalar.

Providers podem ser substituídos.

Componentes podem ser refatorados.

A arquitetura pode evoluir.

Entretanto, essas mudanças devem ocorrer preferencialmente sobre a mesma linha de produto.

---

# 5. LEI WEB FIRST

Todo novo software comercial da Nova FM Tecnologia deve nascer como produto Web desde sua concepção.

Web não é uma etapa posterior, uma migração ou uma segunda implementação do mesmo produto. Pesquisa, referência, descoberta, planejamento, System Design e construção devem considerar desde o início a aplicação Web real que será entregue e operada.

Devem ser considerados desde o planejamento e System Design, conforme aplicável:

- frontend;
- backend;
- APIs;
- autenticação;
- autorização;
- sessões;
- tenant;
- persistência;
- migrations;
- segurança;
- responsividade;
- acessibilidade;
- observabilidade;
- infraestrutura;
- CI/CD;
- deploy;
- domínio;
- HTTPS;
- operação.

Não é aceitável construir deliberadamente uma aplicação local ou interface temporária como produto principal sabendo que posteriormente será necessário reconstruí-la para Web.

Ferramentas locais, scripts, notebooks e interfaces experimentais continuam permitidos para experimentação.

Esses artefatos não constituem o produto comercial. Quando descartáveis, devem ser explicitamente classificados como tal e não podem se transformar silenciosamente na arquitetura principal.

Qualquer exceção à Lei Web First exige necessidade comprovada, análise de impacto, ADR, aprovação humana explícita e plano que preserve uma única linha evolutiva de produto. Conveniência, prazo ou protótipo local não constituem exceção automática.

**WEB FIRST NÃO SIGNIFICA FRONTEND FIRST.**

Significa que toda a cadeia necessária para entregar o produto Web real deve fazer parte da arquitetura desde o princípio.

---

# 6. CLOUD-FIRST

A Nova FM Tecnologia adota estratégia cloud-first.

Sempre que tecnicamente e economicamente adequado, devem ser priorizados em nuvem:

- desenvolvimento;
- ambientes de preview;
- homologação;
- testes;
- bancos;
- armazenamento;
- CI/CD;
- deploy;
- observabilidade;
- automações;
- serviços auxiliares.

A máquina local deve funcionar prioritariamente como estação de desenvolvimento, administração, diagnóstico e acesso.

Containers locais, Docker, WSL e infraestrutura local são opcionais e não constituem requisitos universais da arquitetura FM.

Cloud-first não significa dependência irrestrita de um fornecedor.

Cada decisão relevante deve considerar:

- custo;
- segurança;
- disponibilidade;
- portabilidade;
- complexidade;
- performance;
- capacidade operacional;
- risco de lock-in.

---

# 7. PRODUCT & MARKET BEFORE BUILD

Engenharia eficiente começa antes do código.

Quando aplicável, um novo produto, vertical ou iniciativa comercial deve passar por descoberta de produto e mercado antes da implementação estrutural.

Devem ser investigados proporcionalmente:

- problema real;
- público-alvo;
- necessidade do cliente;
- alternativas atuais;
- concorrentes;
- mercado;
- oportunidade;
- diferenciação;
- proposta de valor;
- disposição a pagar quando possível;
- pricing;
- custos relevantes;
- canais;
- riscos;
- viabilidade comercial;
- viabilidade técnica.

O objetivo não é criar burocracia antes de experimentar.

O objetivo é evitar construir tecnicamente bem um produto cuja justificativa comercial não foi suficientemente investigada.

Hipóteses comerciais devem permanecer identificadas como hipóteses até existir evidência.

---

# 8. CURRENT × TARGET

Nenhuma decisão estrutural deve confundir o que existe com aquilo que pretendemos construir.

Todo trabalho relevante deve distinguir:

## FATO CONFIRMADO

Algo comprovado por código, infraestrutura, documentação canônica, execução, teste ou outra evidência verificável.

## CURRENT

Estado atual comprovado do sistema.

## TARGET

Estado futuro desejado ou aprovado.

## HIPÓTESE

Explicação, possibilidade ou proposta ainda não comprovada.

## PENDÊNCIA

Algo que precisa ser descoberto, decidido, implementado, testado ou validado.

## DECISÃO

Escolha explicitamente aprovada pela autoridade competente.

Um componente presente no System Design Target não deve ser tratado como implementado no Current.

Uma tecnologia planejada não deve ser tratada como instalada.

Uma integração projetada não deve ser tratada como funcional.

Uma funcionalidade implementada não deve ser tratada como homologada.

**TARGET NÃO É CURRENT.**

---

# 9. CURRENT DISCOVERY BEFORE CHANGE

Antes de mudanças relevantes em software existente, deve-se descobrir o Current suficiente para trabalhar com segurança.

Conforme o escopo, isso pode incluir:

- estrutura do repositório;
- código existente;
- módulos;
- contratos;
- APIs;
- schemas;
- migrations;
- autenticação;
- autorização;
- tenancy;
- providers;
- infraestrutura;
- CI/CD;
- testes;
- documentação;
- ADRs;
- System Design;
- dependências;
- autoridades existentes.

Não é necessário auditar o sistema inteiro para corrigir uma função isolada.

A descoberta deve ser proporcional ao impacto.

Pressão por velocidade, entretanto, não autoriza ignorar autoridades, segurança ou evidências.

**VELOCIDADE REDUZ ESCOPO.**

**VELOCIDADE NÃO REDUZ AUTORIDADE, SEGURANÇA OU EVIDÊNCIA.**

---

# 10. AUTORIDADES CANÔNICAS

Cada conceito importante deve possuir autoridade clara.

Exemplos:

- identidade;
- usuário;
- tenant;
- unidade;
- permissões;
- cobrança;
- assinatura;
- agenda;
- pedidos;
- inventário;
- documentos;
- workflow;
- consentimento;
- configurações.

Antes de criar nova representação, serviço, tabela ou regra, deve-se descobrir se já existe autoridade para aquele conceito.

São proibidas sem justificativa arquitetural:

- duas fontes de verdade para o mesmo dado;
- dois sistemas independentes de autenticação para a mesma operação;
- regras de negócio duplicadas no frontend;
- APIs paralelas com regras divergentes;
- schemas concorrentes;
- domínios duplicados;
- serviços novos que silenciosamente assumam autoridade pertencente a outro módulo.

A integração deve preservar autoridades.

Não substituí-las acidentalmente.

---

# 11. FM COGNITIVE VERTICAL CORE

Todo SaaS, software ou sistema construído pela Nova FM Tecnologia deve incorporar o **FM Cognitive Vertical Core**, desde sua arquitetura inicial, como módulo principal de gestão operacional cognitiva.

O Core não é integração posterior.

Não é funcionalidade opcional.

Não é chatbot anexado ao produto.

Não é acessório de interface.

Sua presença, responsabilidades, capacidades, boundaries e relações com as autoridades determinísticas devem ser definidas desde o System Design.

O Core é responsável por compreender e manter contexto operacional, coordenar capacidades, apoiar decisões e orquestrar a operação cognitiva vertical do produto.

A arquitetura conceitual obrigatória é:

**CORE COGNITIVO COMPARTILHADO**  
+  
**CAPACIDADES ESPECÍFICAS DO PRODUTO/VERTICAL**  
+  
**SERVIÇOS DETERMINÍSTICOS**  
+  
**INTERFACES E INTEGRAÇÕES**

O Core deve permitir reutilização de capacidades cognitivas comuns entre produtos sem eliminar as particularidades, regras, autoridades e necessidades de cada vertical.

O Core coordena.

O Core compreende contexto.

O Core recomenda e orquestra.

O Core não substitui silenciosamente serviços determinísticos nem autoridades canônicas.

---

# 12. CORE × AUTORIDADE DETERMINÍSTICA

Inteligência não equivale a autorização.

Uma recomendação, classificação, intenção, score ou decisão sugerida por IA não deve executar automaticamente operações críticas apenas por ter sido produzida pelo Core.

O padrão é:

Core/IA  
→ intenção, análise ou recomendação  
→ política ou contrato aprovado  
→ serviço determinístico autorizado  
→ validações  
→ execução  
→ auditoria.

Um score cognitivo, isoladamente, não constitui autorização operacional.

O serviço responsável deve continuar aplicando:

- identidade;
- autorização;
- tenant;
- estado atual;
- invariantes;
- políticas;
- idempotência;
- limites;
- validações;
- auditoria.

O Core coordena capacidades.

Ele não substitui silenciosamente suas autoridades.

---

# 13. FAIL-CLOSED

Operações críticas devem preferir falha segura.

Quando não houver evidência suficiente para autorizar operação sensível, o sistema não deve presumir autorização.

Aplicável especialmente a:

- identidade;
- autenticação;
- autorização;
- isolamento tenant;
- pagamentos;
- consentimento;
- PII;
- secrets;
- operações destrutivas;
- mudança de privilégios;
- integrações críticas.

Incerteza cognitiva não pode se transformar automaticamente em permissão operacional.

---

# 14. ARQUITETURA PADRÃO DE PRODUTO

Cada produto pode utilizar tecnologias adequadas ao seu problema.

Não existe obrigação de uma única framework, linguagem, banco ou fornecedor.

Entretanto, deve haver separação clara de responsabilidades equivalente às seguintes camadas e capacidades.

## 14.1 Core/Domínio

Regras, modelos, invariantes e contratos centrais.

## 14.2 Application

Casos de uso, coordenação e políticas de aplicação.

## 14.3 Serviços determinísticos

Executam operações com regras verificáveis e autoridades explícitas.

## 14.4 Infraestrutura

Persistência, filas, armazenamento, adapters, providers e recursos externos.

## 14.5 API/HTTP

Expõe casos de uso por contratos controlados.

A API não deve se transformar em domínio paralelo.

## 14.6 Autenticação, autorização e escopo

Identidade, sessão, RBAC/ABAC quando aplicável, tenant, unidade ativa e demais controles devem ser fundação do produto.

## 14.7 Web/UI

Apresenta capacidades ao usuário sem duplicar autoridade do backend.

## 14.8 Dados

Schemas, migrations, constraints, índices, consistência e lifecycle.

## 14.9 Integrações

Providers e serviços externos atrás de boundaries adequados.

## 14.10 Observabilidade

Logs, métricas, health, alertas, tracing quando necessário e auditoria.

## 14.11 Runtime

Ambientes, configuração, secrets, deploy, domínio, HTTPS, recuperação e operação.

---

# 15. SYSTEM DESIGN BEFORE STRUCTURAL IMPLEMENTATION

Mudanças estruturais relevantes devem possuir System Design proporcional ao impacto.

O System Design deve esclarecer quando aplicável:

- objetivo;
- requisitos;
- critérios de aceite;
- Current conhecido;
- Target;
- boundaries;
- componentes;
- autoridades;
- dados;
- contratos;
- fluxos;
- segurança;
- tenancy;
- integrações;
- falhas;
- observabilidade;
- deploy;
- testes;
- riscos;
- decisões pendentes.

System Design não precisa ser um documento gigantesco.

Precisa ser suficiente para impedir implementação estrutural baseada em improvisação.

---

# 16. ARCHITECTURE DECISION RECORDS — ADR

Decisões arquiteturais relevantes devem ser persistidas.

Um ADR deve registrar proporcionalmente:

- contexto;
- problema;
- alternativas conhecidas;
- decisão;
- motivo;
- consequências;
- data;
- autoridade;
- status.

Não se deve fabricar alternativas apenas para preencher documentação.

ADRs existem para impedir que decisões importantes desapareçam junto com o contexto da conversa que as originou.

---

# 17. CONSTITUIÇÃO DE ENGENHARIA DE CÓDIGO

Código é patrimônio operacional da Nova FM Tecnologia.

Toda alteração deve buscar simultaneamente:

- correção;
- clareza;
- segurança;
- testabilidade;
- manutenibilidade;
- compatibilidade;
- rastreabilidade;
- simplicidade proporcional.

O objetivo não é produzir a maior quantidade possível de código.

O objetivo é produzir a menor quantidade de código necessária para implementar corretamente a capacidade aprovada.

Código deve servir à arquitetura.

Arquitetura não deve ser deformada para acomodar código improvisado.

---

# 18. REGRA DA MENOR MUDANÇA COERENTE

Uma tarefa deve realizar a menor alteração que resolva integralmente o problema dentro da arquitetura correta.

Isso não significa criar patches frágeis.

Significa evitar expansão de escopo sem necessidade.

Uma correção de integração não autoriza automaticamente:

- redesign;
- troca de framework;
- reestruturação completa;
- mudança de banco;
- criação de nova API;
- substituição de provider;
- refatoração de módulos não relacionados.

Quando uma alteração maior for realmente necessária, ela deve ser explicitada e aprovada.

---

# 19. PROIBIÇÃO DE REESCRITA POR PREFERÊNCIA

Código existente não deve ser reescrito simplesmente porque outro engenheiro, agente ou modelo faria de forma diferente.

Refatoração deve possuir benefício demonstrável, como:

- corrigir defeito;
- reduzir risco;
- remover dívida relevante;
- habilitar requisito aprovado;
- melhorar segurança;
- resolver problema comprovado de performance;
- reduzir complexidade significativa;
- eliminar duplicação real;
- restaurar aderência arquitetural.

Preferência estética isolada não justifica reescrita estrutural.

---

# 20. PRESERVAÇÃO DE CONTRATOS E BOUNDARIES

Antes de alterar componentes compartilhados, identificar:

- consumidores;
- contratos;
- interfaces;
- eventos;
- schemas;
- dependências;
- compatibilidade.

Mudanças breaking devem ser conscientes e controladas.

Quando necessário, utilizar:

- versionamento;
- compatibilidade progressiva;
- migrations;
- adapters;
- feature flags;
- rollout controlado.

---

# 21. QUALIDADE INTERNA DO CÓDIGO

Todo código novo ou alterado deve respeitar os padrões e convenções estabelecidos no repositório, salvo decisão explícita de mudança.

O código deve buscar:

- legibilidade;
- coesão;
- baixo acoplamento;
- responsabilidade clara;
- nomes compreensíveis;
- fluxo previsível;
- tratamento explícito de erros;
- testabilidade;
- manutenção segura;
- compatibilidade com a arquitetura existente.

Devem ser evitados:

- duplicação desnecessária;
- dead code;
- abstrações prematuras;
- funções ou módulos com responsabilidades excessivamente misturadas;
- complexidade sem benefício demonstrado;
- comentários que apenas repetem o código;
- refatorações cosméticas extensas misturadas com alterações funcionais.

Comentários devem explicar principalmente decisões, limitações ou motivos que não sejam evidentes pela leitura do próprio código.

Uma abstração deve resolver necessidade demonstrada.

Possibilidade hipotética de uso futuro, isoladamente, não justifica aumento de complexidade.

---

# 22. DISCIPLINA DE DEPENDÊNCIAS

Nenhuma biblioteca, framework, serviço ou provider deve ser adicionado apenas por conveniência momentânea.

Antes de adicionar dependência relevante, avaliar:

- necessidade;
- benefício;
- maturidade;
- manutenção;
- segurança;
- licença;
- impacto;
- portabilidade;
- lock-in;
- custo operacional;
- alternativa já existente no projeto.

Uma dependência deve resolver problema real.

---

# 23. CONTROLE DE VERSÃO E GOVERNANÇA DO CÓDIGO

Código-fonte da Nova FM Tecnologia deve permanecer sob controle de versão apropriado.

Conforme o fluxo do projeto, alterações devem utilizar branches, commits, pull requests e mecanismos de revisão adequados.

As mudanças devem buscar:

- commits pequenos e coerentes;
- mensagens compreensíveis;
- escopo identificável;
- diff revisável;
- preservação do histórico;
- rastreabilidade entre requisito, alteração e evidência.

Antes de commit, merge ou integração relevante, o diff deve ser revisado.

Não devem ser misturados silenciosamente em uma mesma alteração:

- feature;
- correção não relacionada;
- redesign;
- refatoração ampla;
- troca tecnológica;
- alteração estrutural não necessária ao objetivo.

É proibido commitar:

- secrets;
- credenciais;
- tokens;
- chaves privadas;
- dados sensíveis indevidos;
- artefatos que não deveriam pertencer ao repositório.

Alterações automatizadas em grande escala devem receber revisão proporcional ao impacto antes da integração.

---

# 24. CÓDIGO PRODUZIDO POR INTELIGÊNCIA ARTIFICIAL

Código gerado, modificado, refatorado ou sugerido por inteligência artificial não possui presunção de correção.

Código produzido por IA está sujeito ao mesmo rigor exigido para qualquer outra alteração de engenharia.

Isso inclui, conforme aplicável:

- aderência ao System Design;
- respeito às autoridades;
- contratos;
- boundaries;
- revisão de diff;
- testes;
- segurança;
- qualidade;
- compatibilidade;
- rastreabilidade;
- evidências;
- gates de homologação;
- gates de produção.

Velocidade de geração não reduz exigência de validação.

Nenhum agente deve expandir silenciosamente seu escopo, redesenhar arquitetura ou introduzir dependências apenas porque consegue produzir rapidamente a implementação.

---

# 25. SEQUÊNCIA OBRIGATÓRIA DE ENGENHARIA

Para alterações relevantes, a sequência padrão é:

**REQUISITO/OBJETIVO**  
→ **CURRENT**  
→ **CRITÉRIOS DE ACEITE**  
→ **IMPACTO**  
→ **IMPLEMENTAÇÃO**  
→ **TESTES**  
→ **REVISÃO DO DIFF**  
→ **SEGURANÇA**  
→ **EVIDÊNCIA**

O nível de formalidade deve ser proporcional ao risco.

O princípio permanece: primeiro compreender suficientemente o que precisa ser alterado e como o resultado será aceito; depois implementar.

Não se deve produzir alteração estrutural extensa para somente depois descobrir requisitos, autoridades ou critérios de aceite.

---

# 26. BACKEND E APIs

Backend é responsável pela execução confiável das regras e casos de uso.

Deve considerar quando aplicável:

- autenticação;
- autorização;
- tenant;
- validação;
- invariantes;
- idempotência;
- concorrência;
- transações;
- retries;
- timeouts;
- falhas parciais;
- erros;
- observabilidade;
- auditoria.

Frontend não deve ser a única barreira de autorização.

Ocultar um botão não protege uma operação.

---

# 27. IDEMPOTÊNCIA E CONCORRÊNCIA

Operações suscetíveis a repetição, retry ou concorrência devem ser projetadas explicitamente.

Especial atenção para:

- pagamentos;
- criação de recursos;
- webhooks;
- jobs;
- filas;
- reservas;
- workflows;
- mudanças de estado;
- integrações externas.

O sistema deve considerar:

- requisições duplicadas;
- execução concorrente;
- retries;
- mensagens fora de ordem;
- timeout após execução;
- respostas parciais.

---

# 28. DADOS E MIGRATIONS

Dados persistentes devem evoluir com segurança.

Antes de migrations relevantes, analisar:

- dados existentes;
- compatibilidade;
- constraints;
- índices;
- integridade referencial;
- impacto operacional;
- rollback ou estratégia de mitigação;
- performance;
- backup quando necessário;
- validação posterior.

Alterações destrutivas silenciosas são proibidas.

Schema Target não deve ser tratado como schema Current.

Cada dado crítico deve possuir autoridade identificável.

---

# 29. MULTI-TENANCY

Quando houver múltiplos clientes, organizações, unidades ou tenants, isolamento deve fazer parte da arquitetura.

A separação não deve depender exclusivamente de filtros no frontend.

Controles devem existir na camada autoritativa adequada.

Acesso cross-tenant não autorizado é falha crítica.

---

# 30. FRONTEND

Frontend é parte integral do produto comercial.

Deve considerar:

- arquitetura de componentes;
- contratos de API;
- estados;
- formulários;
- erros;
- loading;
- empty states;
- sucesso;
- responsividade;
- acessibilidade;
- performance;
- segurança client-side adequada;
- compatibilidade.

Frontend não deve:

- inventar regras do backend;
- possuir secrets;
- tornar-se autoridade de autorização;
- duplicar domínio;
- criar contratos inexistentes.

---

# 31. UX/UI

Experiência de usuário deve fazer parte do produto desde a concepção.

Interfaces devem ser:

- compreensíveis;
- consistentes;
- responsivas;
- acessíveis;
- eficientes;
- adequadas ao público.

Todo fluxo relevante deve considerar estados como:

- loading;
- vazio;
- sucesso;
- erro;
- indisponível;
- parcial;
- desabilitado;
- acesso negado;
- confirmação crítica.

A inteligência do Core deve ser apresentada de maneira que o usuário compreenda quando algo é:

- informação;
- sugestão;
- recomendação;
- incerteza;
- ação pendente;
- confirmação necessária.

---

# 32. MULTI-PROVIDER

A Nova FM Tecnologia deve evitar lock-in desnecessário.

Entretanto:

**MULTI-PROVIDER NÃO SIGNIFICA CRIAR ABSTRAÇÕES PARA TUDO.**

Adapters e boundaries multi-provider devem existir quando houver justificativa técnica, operacional ou comercial.

Considerar:

- risco de dependência;
- custo;
- disponibilidade;
- requisitos do cliente;
- redundância;
- portabilidade;
- negociação comercial;
- evolução futura.

Não construir abstração genérica complexa para um segundo provider hipotético sem necessidade demonstrada.

---

# 33. INTEGRAÇÕES EXTERNAS

Integrações devem considerar:

- contratos;
- autenticação;
- secrets;
- timeouts;
- retries;
- rate limits;
- indisponibilidade;
- respostas inválidas;
- observabilidade;
- versionamento;
- custo;
- quotas.

Webhooks devem considerar:

- autenticidade;
- assinatura;
- replay;
- duplicação;
- idempotência;
- ordem;
- retries;
- auditoria.

---

# 34. SEGURANÇA BY DESIGN

Segurança é fundação, não acabamento.

Conforme o produto, considerar desde o início:

- identidade;
- autenticação;
- autorização;
- sessões;
- RBAC/ABAC;
- least privilege;
- tenant;
- secrets;
- PII;
- consentimento;
- APIs;
- integrações;
- supply chain;
- auditoria;
- abuso;
- vulnerabilidades.

Autenticação não significa autorização universal.

Toda operação crítica deve verificar a autoridade necessária no servidor.

Segurança deve acompanhar todo o ciclo de desenvolvimento.

Ela não deve aparecer apenas quando a implementação já estiver concluída.

---

# 35. SECRETS

Secrets não devem ser armazenados em:

- código-fonte;
- repositórios;
- frontend;
- prompts;
- logs;
- documentação pública;
- screenshots compartilhados sem controle.

Devem utilizar mecanismos apropriados de configuração e secret management.

---

# 36. TESTES

Testes devem ser proporcionais ao risco e à criticidade.

Conforme a funcionalidade, considerar:

- unitários;
- aplicação;
- integração;
- contratos;
- API;
- frontend;
- E2E;
- regressão;
- segurança;
- autorização;
- tenant;
- migrations;
- performance;
- smoke.

Caminhos negativos são parte da qualidade.

Testar apenas happy path não é suficiente para operações críticas.

---

# 37. CENÁRIOS DE FALHA

Quando aplicável, testar:

- entrada inválida;
- ausência de dados;
- usuário não autenticado;
- usuário sem permissão;
- tenant incorreto;
- duplicação;
- concorrência;
- timeout;
- retry;
- provider indisponível;
- resposta externa inválida;
- migration parcial;
- falha de rede;
- estado inesperado;
- regressão.

---

# 38. QUALIDADE DE IA

Capacidades cognitivas possuem características diferentes de serviços determinísticos.

Testes devem avaliar:

- contrato de saída;
- comportamento diante de contexto insuficiente;
- respostas inválidas;
- incerteza;
- timeout;
- fallback;
- limites de autoridade;
- segurança;
- recuperação.

Não se deve transformar comportamento probabilístico em autorização crítica sem camada determinística apropriada.

---

# 39. GATE FINAL DE SEGURANÇA

Segurança deve acompanhar todo o ciclo de desenvolvimento e ser novamente verificada antes da liberação para produção.

Toda funcionalidade ou release deve passar por auditoria final de segurança proporcional ao seu risco antes de ser disponibilizado ao cliente.

Conforme aplicável, essa auditoria deve verificar:

- autenticação;
- autorização;
- isolamento tenant;
- identidade;
- sessão;
- privilégios;
- PII;
- consentimento;
- secrets;
- APIs;
- integrações;
- webhooks;
- dependências;
- supply chain;
- configuração cloud;
- logs;
- operações destrutivas;
- pagamentos;
- migrations;
- exposição de dados;
- superfícies de abuso.

Devem ser utilizados testes adversariais proporcionais à criticidade da funcionalidade.

Constituem **STOP DE PRODUÇÃO**, entre outros riscos críticos aplicáveis:

- cross-tenant access não autorizado;
- bypass de autenticação ou autorização;
- escalada indevida de privilégios;
- exposição de secrets;
- vazamento relevante de dados;
- possibilidade crítica de fraude;
- corrupção de dados;
- execução destrutiva não autorizada;
- vulnerabilidade crítica conhecida sem tratamento adequado.

FM Security Engineer, FM QA Engineer e FM DevOps/SRE devem fornecer evidências complementares para os gates sob suas respectivas autoridades.

FM QA Engineer não deve homologar ignorando um STOP de segurança.

FM Documentation & Release Manager não deve registrar como pronto para produção um release cujo gate obrigatório permaneça pendente.

Um release não será considerado **PRONTO PARA PRODUÇÃO** enquanto os controles obrigatórios de segurança aplicáveis não tiverem sido verificados ou enquanto existir risco crítico conhecido sem tratamento formalmente aprovado.

O objetivo institucional é detectar e corrigir vulnerabilidades antes que o cliente utilize o sistema, reduzindo falhas previsíveis e correções emergenciais em produção.

Auditoria prévia reduz risco, mas não estabelece segurança absoluta.

Por isso, monitoramento, observabilidade, gestão de vulnerabilidades e capacidade de resposta a incidentes permanecem obrigatórios após o release.

---

# 40. DIFF AUDITÁVEL

Mudanças relevantes devem permitir compreensão do que foi alterado.

Antes da integração, deve ser possível responder:

- o que mudou?
- por quê?
- quais arquivos?
- quais contratos?
- quais dados?
- quais riscos?
- quais testes?
- quais evidências?
- existe impacto de segurança?
- existe impacto operacional?
- existe migration?
- existe breaking change?

Alterações gigantescas e desnecessariamente misturadas dificultam revisão e aumentam risco.

---

# 41. CI/CD

Pipelines devem tornar integração e deploy:

- reproduzíveis;
- rastreáveis;
- seguros;
- verificáveis.

Gates aplicáveis podem incluir:

- lint;
- typecheck;
- unit tests;
- integration tests;
- contract tests;
- frontend tests;
- build;
- security checks;
- migration validation;
- tenant isolation;
- E2E;
- smoke.

Falha em gate obrigatório bloqueia progressão até resolução ou exceção formalmente aprovada.

---

# 42. AMBIENTES

Development, preview/homologação e produção devem utilizar a mesma linha arquitetural.

Diferenças devem ser principalmente de:

- configuração;
- credenciais;
- endpoints;
- dados;
- capacidade;
- políticas;
- observabilidade;
- providers sandbox/production.

Não devem existir como produtos tecnologicamente independentes que exijam reconstrução para promoção.

---

# 43. DEPLOY NÃO SIGNIFICA SUCESSO

Uma aplicação ter sido implantada não significa que está operacionalmente saudável.

Após deploy, conforme criticidade, verificar:

- health;
- inicialização;
- migrations;
- logs;
- erros;
- integrações;
- jornadas críticas;
- métricas;
- regressões;
- disponibilidade.

---

# 44. OBSERVABILIDADE

Sistemas devem produzir evidência operacional proporcional à importância.

Considerar:

- logs estruturados;
- métricas;
- healthchecks;
- alertas;
- tracing quando útil;
- auditoria.

Logs não devem expor secrets ou PII desnecessária.

Observabilidade também deve auxiliar detecção de comportamento anômalo e incidentes de segurança.

---

# 45. BACKUP E RECUPERAÇÃO

Backup existente não equivale automaticamente a recuperação comprovada.

Sistemas críticos devem definir proporcionalmente:

- o que é salvo;
- frequência;
- retenção;
- proteção;
- restauração;
- responsáveis;
- testes de recuperação.

Quando recuperação for requisito crítico, sua validação deve produzir evidência.

---

# 46. INCIDENTES E VULNERABILIDADES PÓS-PRODUÇÃO

Validação prévia rigorosa reduz risco, mas não elimina integralmente a possibilidade de defeitos ou vulnerabilidades futuras.

Quando incidente ocorrer:

1. proteger usuários, dados e operação;
2. estabilizar o sistema;
3. preservar evidências;
4. distinguir fatos de hipóteses;
5. aplicar mitigação ou rollback quando adequado;
6. investigar causa;
7. corrigir;
8. testar a correção;
9. verificar regressões;
10. documentar;
11. incorporar aprendizado ao processo quando necessário.

Produção não deve ser utilizada como substituto dos testes pré-release.

Incidentes reais, entretanto, devem gerar aprendizado institucional.

---

# 47. PROTÓTIPOS

Protótipos continuam permitidos.

Devem ser classificados explicitamente como:

**PROTÓTIPO DESCARTÁVEL — NÃO É BASE DE PRODUÇÃO**

quando não obedecerem à arquitetura comercial.

Um protótipo somente deve ser promovido à linha oficial após avaliação de compatibilidade arquitetural.

Experimentação deve acelerar aprendizado.

Não deve criar dívida estrutural silenciosa.

---

# 48. DEFINITION OF DONE COMERCIAL

Uma funcionalidade comercial não está concluída apenas porque sua lógica funciona.

A cadeia aplicável pode envolver:

Core/Domínio  
→ Application  
→ serviços determinísticos  
→ infraestrutura  
→ persistência/migrations  
→ API  
→ autenticação/autorização  
→ tenant  
→ Web/UI  
→ testes  
→ segurança  
→ CI/CD  
→ homologação  
→ deploy  
→ operação.

Cada projeto deve definir seu Definition of Done proporcional.

---

# 49. ESTADOS DE PRONTIDÃO

A palavra **PRONTO** nunca deve ser utilizada sem contexto.

## IMPLEMENTADO

O código correspondente existe.

## INTEGRADO

Os componentes necessários funcionam conjuntamente.

## TESTADO

Os testes aplicáveis foram executados com evidência.

## HOMOLOGADO

Os critérios de aceite foram comprovados.

## PRONTO PARA PRODUÇÃO

Gates técnicos, de segurança, dados, operação e release aplicáveis foram satisfeitos.

## COMERCIALMENTE DISPONÍVEL

O produto pode ser entregue, vendido, operado e suportado no contexto definido.

Esses estados não são sinônimos.

---

# 50. EVIDÊNCIA

Afirmações importantes de estado devem possuir evidência proporcional.

Exemplos:

- resultado de teste;
- CI;
- logs;
- execução;
- diff;
- commit;
- PR;
- relatório;
- checklist;
- resultado de security gate;
- resultado de homologação;
- screenshot quando apropriado.

Uma captura de tela isolada não prova automaticamente todo o comportamento de um sistema.

---

# 51. RASTREABILIDADE

Sempre que aplicável, deve ser possível seguir:

necessidade/problema  
→ pesquisa/validação  
→ requisito  
→ decisão  
→ System Design/ADR  
→ implementação  
→ testes  
→ segurança  
→ homologação  
→ evidência  
→ release  
→ documentação.

A rastreabilidade protege o projeto contra perda de contexto e decisões contraditórias.

---

# 52. DOCUMENTAÇÃO

Cada projeto deve manter documentação proporcional à sua complexidade.

Pode incluir:

- Documento Mestre;
- pesquisa Product & Market;
- requisitos;
- System Design;
- Arquitetura Mestre;
- ADRs;
- contratos;
- schemas;
- inventário de capacidades;
- backlog;
- testes;
- segurança;
- runbooks;
- changelog;
- releases;
- dívidas;
- handoffs.

Documentação deve refletir o sistema real.

Não deve apresentar Target como Current.

Não deve registrar teste não executado como aprovado.

Não deve registrar release não homologado como pronto.

---

# 53. FONTE DE VERDADE ORGANIZACIONAL

A fonte de verdade organizacional local da Nova FM Tecnologia é:

`C:\Nova-FM-Tecnologia`

Documentos e artefatos canônicos devem possuir localização clara dentro da estrutura organizacional.

Não devem ser criadas cópias paralelas sem necessidade, pois isso fragmenta a autoridade documental.

Código-fonte deve utilizar seu repositório e sistema de versionamento correspondente como autoridade técnica.

---

# 54. FÁBRICA DE SOFTWARE DA NOVA FM TECNOLOGIA

A fábrica de software institucional atual da Nova FM Tecnologia é centralizada no ecossistema OpenAI/ChatGPT e organizada por especialistas.

Sua estrutura atual é:

1. FM SaaS Tech Lead
2. FM Product & Market
3. FM Solution Architect
4. FM Cognitive Vertical Core
5. FM Frontend Engineer
6. FM Backend/API Engineer
7. FM Data Engineer
8. FM Integration & Providers Engineer
9. FM Security Engineer
10. FM QA Engineer
11. FM DevOps/SRE
12. FM UX/UI Designer
13. FM Documentation & Release Manager

Essa estrutura organiza responsabilidades.

Não cria treze autoridades concorrentes.

A adoção futura de outros agentes, modelos ou mecanismos de orquestração será tratada separadamente e não altera automaticamente esta norma.

---

# 55. AUTORIDADE DOS ESPECIALISTAS

## 55.1 FM SaaS Tech Lead

Coordena decisões técnicas transversais, execução e coerência global.

## 55.2 FM Product & Market

Responsável por pesquisa de mercado, problema, requisitos, oportunidade, posicionamento e análise comercial.

## 55.3 FM Solution Architect

Responsável por arquitetura, boundaries, System Design e decisões estruturais.

## 55.4 FM Cognitive Vertical Core

Responsável pela coordenação cognitiva vertical, contexto operacional e orquestração das capacidades do produto, preservando autoridades determinísticas.

## 55.5 FM Frontend Engineer

Responsável pela engenharia frontend.

## 55.6 FM Backend/API Engineer

Responsável por serviços determinísticos, backend e APIs.

## 55.7 FM Data Engineer

Responsável por modelagem, persistência, migrations, integridade e evolução dos dados.

## 55.8 FM Integration & Providers Engineer

Responsável por integrações, adapters, providers e estratégia multi-provider.

## 55.9 FM Security Engineer

Responsável por requisitos, análise, auditoria e gates de segurança.

## 55.10 FM QA Engineer

Responsável por estratégia de testes, regressão, evidências e homologação.

## 55.11 FM DevOps/SRE

Responsável por cloud, CI/CD, deploy, observabilidade, confiabilidade, recuperação e operação.

## 55.12 FM UX/UI Designer

Responsável por experiência, fluxos, design system, responsividade e acessibilidade.

## 55.13 FM Documentation & Release Manager

Responsável por documentação, rastreabilidade, changelog, releases e readiness documental.

---

# 56. COORDENAÇÃO NÃO É USURPAÇÃO

Um especialista não deve assumir silenciosamente a autoridade de outro.

Exemplos:

- prazo comercial não decide arquitetura;
- frontend não decide autorização;
- IA não decide pagamento sozinha;
- QA não redefine requisito;
- DevOps não redefine domínio;
- Product não implementa arquitetura por conveniência;
- Core não substitui serviços autoritativos;
- Backend não redefine sozinho experiência de produto;
- Architect não declara homologação sem evidência de QA;
- Documentation & Release não declara produção pronta com gate obrigatório pendente.

Conflitos devem subir para a autoridade apropriada.

---

# 57. FLUXO PADRÃO DE UM NOVO PRODUTO

Conforme aplicável:

Descoberta  
→ Product & Market  
→ problema/oportunidade validável  
→ requisitos e critérios de aceite  
→ Target  
→ System Design  
→ arquitetura aprovada  
→ Core e capacidades  
→ backlog incremental  
→ implementação  
→ testes  
→ revisão de código/diff  
→ auditoria de segurança aplicável  
→ integração  
→ homologação  
→ readiness operacional  
→ autorização de release  
→ produção  
→ monitoramento  
→ evolução contínua.

O fluxo pode ser simplificado para projetos pequenos.

Os princípios não devem ser silenciosamente descartados.

---

# 58. FLUXO PADRÃO DE ALTERAÇÃO EM PRODUTO EXISTENTE

Objetivo  
→ Current Discovery proporcional  
→ autoridade existente  
→ requisitos e critérios de aceite  
→ impacto  
→ decisão  
→ menor mudança coerente  
→ implementação  
→ testes  
→ revisão do diff  
→ auditoria de segurança aplicável  
→ homologação  
→ readiness operacional  
→ deploy  
→ monitoramento  
→ evidência  
→ documentação.

---

# 59. GATES

Gates existem para impedir que risco desconhecido avance silenciosamente.

Conforme o projeto, podem existir gates de:

- Current Discovery;
- produto;
- arquitetura;
- código;
- dados;
- segurança;
- QA;
- integração;
- operação;
- release;
- produção.

Nem toda alteração exige todos os gates.

A intensidade deve acompanhar o risco.

Gate obrigatório não deve ser ignorado silenciosamente.

---

# 60. STOP CONDITIONS

A execução deve parar e escalar quando surgir, por exemplo:

- conflito de autoridade;
- alteração arquitetural não aprovada;
- risco crítico de segurança;
- possibilidade relevante de perda de dados;
- cross-tenant access;
- operação financeira sem autoridade clara;
- migration destrutiva não planejada;
- necessidade de expor secret;
- contrato crítico desconhecido;
- evidência contraditória;
- expansão substancial de escopo;
- necessidade de criar arquitetura paralela;
- vulnerabilidade crítica conhecida;
- bypass de autorização;
- alteração destrutiva não autorizada.

STOP não significa abandonar a tarefa.

Significa impedir improvisação irreversível.

---

# 61. EVOLUÇÃO SEM RECONSTRUÇÃO

Produtos devem evoluir preferencialmente através de:

- módulos;
- capabilities;
- refatorações controladas;
- migrations;
- adapters;
- contratos;
- APIs versionadas;
- feature flags;
- filas/eventos;
- rollout progressivo;
- substituição incremental.

Reescrita total exige justificativa técnica e econômica explícita e aprovação humana.

---

# 62. VISUAL PREMIUM

Qualidade visual pode evoluir progressivamente.

Entretanto, acabamento premium deve ocorrer sobre a mesma linha comercial do produto.

Não se deve construir segunda aplicação apenas para obter interface melhor.

UX/UI evolui.

A arquitetura permanece coerente.

---

# 63. READINESS COMERCIAL

Um produto comercial deve ser analisado além do código.

Quando aplicável, readiness inclui:

- funcionalidade;
- UX;
- segurança;
- dados;
- infraestrutura;
- observabilidade;
- suporte;
- documentação;
- pricing;
- operação;
- onboarding;
- capacidade de entrega;
- estabilidade;
- requisitos comerciais.

Produto tecnicamente sofisticado não é automaticamente produto comercialmente pronto.

---

# 64. PROIBIÇÕES INSTITUCIONAIS DE RETRABALHO E DUPLICAÇÃO

Salvo exceção formalmente aprovada, ficam proibidos:

- criar segundo domínio para substituir domínio funcional existente sem necessidade comprovada;
- duplicar regras de negócio no frontend;
- criar APIs paralelas com regras diferentes;
- manter dois sistemas de autenticação para a mesma operação sem necessidade arquitetural;
- criar segunda fonte de verdade para tenant, unidade, usuário ou permissões;
- implementar sistema temporário que já se sabe que será descartado antes da comercialização;
- criar nova UI em outra tecnologia apenas para migrá-la depois;
- manter schemas independentes sem estratégia de evolução;
- instalar infraestrutura ou dependências sem necessidade real;
- expandir migração ou integração para redesign não autorizado;
- introduzir abstrações apenas por possibilidade futura;
- substituir provider funcional apenas por preferência;
- alterar arquitetura transversal dentro de tarefa local sem decisão correspondente.

---

# 65. GOVERNANÇA DE MUDANÇAS

Esta norma deve evoluir quando experiência real demonstrar necessidade.

Mudanças no Documento Mestre devem:

1. possuir motivo;
2. preservar histórico;
3. identificar decisão;
4. registrar data;
5. evitar edição silenciosa de princípios;
6. gerar nova versão quando materialmente relevante.

A norma não deve congelar a empresa.

Deve impedir que a empresa esqueça o que aprendeu.

---

# 66. EXCEÇÕES

Uma regra pode possuir exceção quando realidade técnica, econômica ou comercial justificar.

Exceções relevantes devem ser explícitas.

Uma exceção não cria automaticamente novo padrão institucional.

Para tornar-se padrão, deve passar por decisão específica.

---

# 67. REGRA CONSTITUCIONAL RESUMIDA

1. Investigar e validar o problema antes de construir quando aplicável.
2. Construir na linha arquitetural comercial pretendida.
3. Construir todo novo software comercial como Web First desde a concepção.
4. Adotar cloud-first sem dependência local desnecessária.
5. Utilizar Arquitetura Única Evolutiva.
6. Incorporar o FM Cognitive Vertical Core em todo software FM desde o System Design.
7. Manter inteligência separada de autoridade determinística.
8. Descobrir Current antes de alterar sistemas existentes.
9. Nunca confundir Target com Current.
10. Preservar autoridades canônicas.
11. Não criar arquitetura paralela sem necessidade comprovada.
12. Não duplicar domínio, regras, APIs, schemas ou autenticação.
13. Fazer a menor mudança coerente.
14. Não reescrever código por preferência.
15. Preservar contratos e boundaries.
16. Manter qualidade interna do código.
17. Manter código sob controle de versão e revisar diffs.
18. Aplicar ao código produzido por IA o mesmo rigor de qualquer outro código.
19. Tratar dados e migrations como patrimônio.
20. Segurança nasce com o produto.
21. Operações críticas devem falhar de forma segura.
22. Auditar segurança novamente antes da produção conforme o risco.
23. Bloquear produção diante de STOP crítico.
24. Testar proporcionalmente ao risco.
25. Não declarar pronto sem evidência.
26. Deploy não significa saúde operacional.
27. Documentar decisões importantes.
28. Manter rastreabilidade.
29. Usar multi-provider quando houver justificativa, não como abstração artificial.
30. Evoluir incrementalmente.
31. Monitorar e aprender após produção.
32. Preservar tempo, capital, contexto e conhecimento institucional.

---

# 68. DECLARAÇÃO DE FUNDAÇÃO

A Nova FM Tecnologia constrói produtos para durar e evoluir.

Cada novo software deve nascer consciente de seu mercado, de sua arquitetura comercial, de suas autoridades, de seus dados, de sua segurança, de sua operação e de sua evolução.

A inteligência artificial deve ampliar capacidade humana e operacional sem destruir governança.

O FM Cognitive Vertical Core deve estar presente desde a arquitetura inicial de todo software FM como seu módulo principal de gestão operacional cognitiva, sem substituir as autoridades determinísticas que protegem usuários, dados e operações.

Código deve ser tratado como patrimônio.

Código produzido por inteligência artificial deve ser auditado, testado e protegido com o mesmo rigor exigido para qualquer implementação.

Arquitetura deve reduzir retrabalho.

Segurança deve nascer com o produto e ser novamente verificada antes que o produto alcance o cliente.

Testes devem produzir confiança.

Evidência deve sustentar afirmações.

Documentação deve preservar contexto.

Cloud deve ampliar capacidade operacional sem criar dependência desnecessária.

Cada especialista deve exercer sua responsabilidade sem criar autoridade concorrente.

Cada versão deve aumentar o valor acumulado do produto em vez de preparar a próxima reconstrução.

Produção não deve ser utilizada como ambiente para descobrir falhas previsíveis que poderiam ter sido identificadas antes do release.

Ao mesmo tempo, nenhum sistema deve presumir risco zero: observabilidade, monitoramento, gestão de vulnerabilidades e capacidade de resposta permanecem parte da responsabilidade operacional após a publicação.

**CONSTRUIR UMA VEZ.**

**CONSTRUIR NA ESTRUTURA CERTA.**

**VALIDAR ANTES DE ESCALAR.**

**PRESERVAR AUTORIDADES.**

**PROTEGER ANTES DE PUBLICAR.**

**PROVAR ANTES DE DECLARAR PRONTO.**

**EVOLUIR SEM RECONSTRUIR.**

---

# 69. REGISTRO DE VERSÃO

## Versão 1.0 — 13/09/2026

Instituição da Arquitetura Única Evolutiva como fundação de engenharia da FM Tecnologia.

Estabeleceu, entre outros fundamentos:

- linha única de produto;
- arquitetura comercial desde a fundação;
- Definition of Done Comercial;
- Web/UI como parte da entrega;
- segurança como fundação;
- testes e gates;
- infraestrutura planejada desde o início;
- governança de agentes;
- documentação;
- evolução sem reconstrução;
- métricas de prontidão;
- aprendizado institucional derivado do Kordena.

## Versão 2.0 — 17/09/2026

Reescrita e consolidação da norma institucional.

Incorpora e reforça:

- Web First;
- cloud-first;
- Product & Market antes da implementação quando aplicável;
- Current × Target;
- autoridades canônicas;
- FM Cognitive Vertical Core obrigatório em todo software FM;
- separação entre cognição e autoridade determinística;
- fail-closed;
- System Design;
- ADRs;
- constituição ampliada de engenharia de código;
- menor mudança coerente;
- proibição de reescrita por preferência;
- qualidade interna do código;
- governança de dependências;
- controle de versão;
- revisão de diff;
- código produzido por IA sujeito ao mesmo rigor;
- backend e APIs;
- idempotência e concorrência;
- dados e migrations;
- multi-tenancy;
- frontend e UX/UI;
- multi-provider quando justificado;
- integrações;
- segurança by design;
- Gate Final de Segurança;
- STOP de produção;
- testes;
- CI/CD;
- observabilidade;
- recuperação;
- resposta a incidentes;
- evidência;
- rastreabilidade;
- readiness comercial;
- fábrica especializada atual da Nova FM Tecnologia.

---

**NOVA FM TECNOLOGIA**

**DOCUMENTO MESTRE DE FUNDAÇÃO — V2.0**

**NORMA MESTRE OBRIGATÓRIA**

**17/09/2026**
