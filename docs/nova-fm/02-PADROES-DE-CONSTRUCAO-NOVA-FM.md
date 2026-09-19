# NOVA FM TECNOLOGIA
# PADRÕES DE CONSTRUÇÃO DE SOFTWARE
## Manual Operacional do FM SaaS Builder

**Arquivo:** `02-PADROES-DE-CONSTRUCAO-NOVA-FM.md`  
**Status:** NORMA OPERACIONAL DE ENGENHARIA  
**Aplicabilidade:** Todos os produtos, SaaS, sistemas e serviços construídos pela Nova FM Tecnologia  
**Subordinado a:** Documento Mestre da Nova FM Tecnologia v2.0  
**Responsável primário de execução:** FM SaaS Builder  
**Próxima estação da esteira:** FM Audit & Fix  

---

# 1. PROPÓSITO

Este documento estabelece os padrões técnicos e operacionais que orientam a construção de software pela Nova FM Tecnologia.

Ele transforma os princípios institucionais do Documento Mestre em práticas concretas de engenharia para:

- arquitetura;
- desenvolvimento;
- frontend;
- backend;
- APIs;
- dados;
- integrações;
- providers;
- segurança por construção;
- testes;
- Git e GitHub;
- CI/CD;
- observabilidade;
- documentação;
- evidências;
- handoff;
- readiness técnico.

O objetivo não é impor tecnologia específica sem necessidade.

O objetivo é garantir que qualquer produto Nova FM seja construído de forma:

- rastreável;
- testável;
- sustentável;
- evolutiva;
- segura;
- modular;
- auditável;
- comercialmente preparada;
- resistente a perda de contexto;
- resistente a lock-in desnecessário.

---

# 2. HIERARQUIA DE AUTORIDADE

A hierarquia obrigatória é:

Documento Mestre Nova FM Tecnologia  
→ Padrões de Construção Nova FM  
→ System Design e ADRs aprovados  
→ contratos e especificações do produto  
→ implementação  
→ evidências técnicas  
→ auditoria independente

Em caso de conflito entre este documento e o Documento Mestre, prevalece sempre o Documento Mestre.

Em caso de conflito entre conhecimento geral de IA e norma institucional Nova FM, prevalece a norma Nova FM.

Em caso de conflito entre documentação histórica e CURRENT técnico comprovado, o conflito deve ser registrado e reconciliado.

Nenhum chat antigo, handoff antigo, documento legado ou memória informal possui autoridade automática sobre o estado técnico atual.

---

# 3. CURRENT ANTES DE TARGET

Nenhuma mudança relevante deve ser iniciada sem compreensão suficiente do CURRENT.

Antes de construir, o Builder deve identificar, quando aplicável:

- repositório;
- branch padrão;
- branch de trabalho;
- PR em andamento;
- último commit relevante;
- arquitetura existente;
- serviços;
- banco;
- contratos;
- integrações;
- workflows;
- CI;
- estado dos testes;
- documentação vigente;
- decisões arquiteturais existentes.

Toda análise deve diferenciar explicitamente:

**FATO CONFIRMADO**  
Informação sustentada por evidência verificável.

**HIPÓTESE**  
Interpretação ainda não confirmada.

**DECISÃO**  
Escolha formalmente adotada.

**TARGET**  
Estado desejado.

**PENDÊNCIA**  
Informação, decisão, implementação ou evidência ainda faltante.

TARGET nunca deve ser apresentado como CURRENT.

---

# 4. WEB FIRST

Todo novo software comercial da Nova FM Tecnologia deve nascer como produto web desde o início.

Web não é fase posterior, migração nem segunda construção. Pesquisa, referência, descoberta, planejamento, System Design, implementação, testes, homologação e operação devem pertencer à mesma linha evolutiva do produto web real.

Web First não significa Frontend First.

Um produto web deve ser concebido como sistema completo:

domínio  
→ contratos  
→ dados  
→ serviços  
→ APIs  
→ segurança  
→ frontend  
→ integrações  
→ observabilidade  
→ operação

Não construir primeiro uma solução incompatível com web para depois reescrevê-la.

Ferramentas locais, scripts, notebooks e protótipos são permitidos somente como apoio experimental explicitamente descartável. Não podem ser tratados como primeira versão comercial nem se tornar silenciosamente a arquitetura principal.

Qualquer exceção exige necessidade comprovada, análise de impacto, ADR e aprovação humana explícita antes da implementação.

A arquitetura inicial deve considerar desde o começo:

- execução em navegador;
- autenticação web;
- autorização;
- responsividade;
- acessibilidade;
- APIs;
- segurança;
- tenancy;
- deploy;
- atualização contínua;
- telemetria;
- escalabilidade adequada ao produto.

---

# 5. CLOUD-FIRST

A Nova FM Tecnologia opera prioritariamente em modelo cloud-first.

Devem ser priorizados em nuvem, quando aplicável:

- desenvolvimento;
- preview;
- ambientes;
- banco;
- testes;
- CI;
- CD;
- deploy;
- armazenamento;
- automações;
- observabilidade;
- serviços auxiliares.

Containers locais não são requisito obrigatório.

Docker local não deve ser introduzido como dependência operacional se não houver necessidade concreta.

A estação local deve permanecer leve sempre que possível.

---

# 6. SYSTEM DESIGN

Mudanças estruturais devem ser precedidas por System Design proporcional ao risco e à complexidade.

O System Design deve responder, quando aplicável:

- qual problema será resolvido;
- qual é o CURRENT;
- qual é o TARGET;
- quais componentes serão afetados;
- quais contratos serão criados ou alterados;
- quais dados serão afetados;
- quais integrações serão afetadas;
- quais riscos existem;
- como ocorrerá deploy;
- como ocorrerá rollback;
- quais evidências serão necessárias.

O System Design deve evitar excesso de abstração.

Design existe para reduzir incerteza e risco, não para produzir documentação ornamental.

---

# 7. ARCHITECTURE DECISION RECORDS — ADR

Decisões arquiteturais relevantes e difíceis de reverter devem possuir ADR.

Um ADR deve registrar:

- contexto;
- decisão;
- alternativas consideradas;
- motivo da escolha;
- consequências;
- riscos;
- data;
- status.

ADRs devem ser preservados como histórico.

Decisão substituída não deve ser apagada; deve ser marcada como superseded quando aplicável.

---

# 8. ARQUITETURA ÚNICA E EVOLUTIVA

Evitar arquiteturas paralelas sem necessidade.

Um produto deve evoluir sobre uma arquitetura coerente.

Mudanças devem preferir evolução incremental a reescritas completas.

Reescrita total só deve ocorrer quando houver justificativa técnica forte.

Priorizar:

- baixo acoplamento;
- alta coesão;
- separação de responsabilidades;
- contratos explícitos;
- evolução incremental;
- testabilidade;
- observabilidade;
- reversibilidade.

---

# 9. ESTRUTURA DE PROJETO

Projetos devem possuir organização previsível.

A estrutura real depende da stack, mas responsabilidades devem permanecer identificáveis.

Separar conceitualmente:

- domínio;
- aplicação;
- infraestrutura;
- interfaces;
- integrações;
- configuração;
- testes;
- documentação.

Evitar diretórios genéricos utilizados como depósitos indiscriminados.

Estrutura deve ajudar um novo engenheiro ou agente a compreender rapidamente:

- onde está a regra de negócio;
- onde estão contratos;
- onde estão integrações;
- onde estão persistência e migrations;
- onde estão testes;
- onde estão configurações.

---

# 10. CONSTITUIÇÃO DE CÓDIGO

Código Nova FM deve ser:

- claro;
- legível;
- explícito;
- modular;
- testável;
- rastreável;
- revisável;
- consistente;
- seguro;
- sustentável.

Evitar:

- funções excessivamente grandes;
- duplicação significativa;
- dependências circulares;
- estados implícitos;
- efeitos colaterais escondidos;
- código morto;
- comentários que contradizem implementação;
- configuração crítica hardcoded;
- segredos no código.

Código gerado por IA está sujeito ao mesmo padrão de qualidade de código produzido manualmente.

IA não reduz exigência de revisão.

---

# 11. NOMENCLATURA

Nomes devem transmitir intenção.

Evitar:

- nomes vagos;
- abreviações obscuras;
- variáveis genéricas;
- entidades com múltiplos significados.

Preferir nomes derivados do domínio do produto.

O vocabulário técnico deve permanecer consistente entre:

- código;
- APIs;
- banco;
- documentação;
- interface;
- observabilidade.

---

# 12. DEPENDÊNCIAS

Toda dependência relevante deve possuir justificativa.

Antes de adicionar biblioteca, SDK ou serviço externo, avaliar:

- maturidade;
- manutenção;
- segurança;
- licença;
- tamanho;
- lock-in;
- custo;
- compatibilidade;
- necessidade real.

Não adicionar dependência pesada para resolver problema simples.

Não reimplementar solução complexa quando existe componente maduro e adequado.

---

# 13. FRONTEND

O frontend deve nascer preparado para ambiente web real.

Deve ser:

- responsivo;
- acessível;
- performático;
- previsível;
- consistente;
- observável;
- integrado a contratos reais.

Separar claramente:

- apresentação;
- estado;
- comunicação;
- domínio quando aplicável.

Não manter regra crítica exclusivamente no cliente.

Autorização não pode depender somente da interface.

O backend deve continuar sendo autoridade para operações protegidas.

---

# 14. ESTADOS DE INTERFACE

Toda experiência relevante deve tratar estados explicitamente:

- loading;
- empty;
- success;
- partial;
- error;
- unavailable;
- unauthorized;
- forbidden.

Não deixar interface silenciosamente quebrada.

Erros devem permitir diagnóstico sem exposição indevida de detalhes internos.

---

# 15. ACESSIBILIDADE

Acessibilidade é requisito de construção.

Considerar:

- navegação por teclado;
- contraste;
- foco;
- labels;
- semântica;
- leitores de tela;
- feedback de erro;
- tamanho de controles;
- responsividade.

Acessibilidade não deve ser tratada apenas como acabamento posterior.

---

# 16. RESPONSIVIDADE

Interfaces comerciais web devem funcionar adequadamente nos tamanhos relevantes para o produto.

O layout deve considerar pelo menos:

- desktop;
- notebook;
- tablet quando aplicável;
- mobile quando aplicável.

Evitar interface construída exclusivamente para resolução de desenvolvimento.

---

# 17. DESIGN SYSTEM

Quando o produto possuir escala visual relevante, utilizar design system ou conjunto consistente de tokens e componentes.

Padronizar, quando aplicável:

- cores;
- tipografia;
- espaçamento;
- radius;
- sombras;
- estados;
- componentes;
- feedback;
- ícones.

O FM Premium UX/UI é responsável pelo refinamento premium.

O Builder é responsável por garantir coerência estrutural e funcional suficiente para essa etapa.

---

# 18. BACKEND

Backend deve separar:

- regras de domínio;
- casos de uso;
- infraestrutura;
- acesso a dados;
- providers;
- transporte/API.

Evitar regra de negócio dispersa em controllers, handlers ou componentes de infraestrutura.

Serviços críticos devem possuir comportamento previsível e auditável.

---

# 19. APIs

APIs devem possuir contratos explícitos.

Definir:

- entrada;
- saída;
- erros;
- autenticação;
- autorização;
- versionamento quando necessário;
- limites;
- idempotência quando aplicável.

Entradas devem ser validadas.

Erros devem ser tratados de forma previsível.

Não retornar informações sensíveis desnecessárias.

---

# 20. VERSIONAMENTO DE API

Alterações breaking devem ser evitadas ou versionadas quando necessário.

Antes de alterar contrato existente, identificar consumidores.

Mudanças devem considerar compatibilidade.

Quando breaking change for inevitável, produzir plano de transição.

---

# 21. AUTENTICAÇÃO

Autenticação deve ser tratada como infraestrutura crítica.

Não criar mecanismos próprios de autenticação sem justificativa forte.

Credenciais, tokens e sessões devem ser tratados com segurança.

Não registrar tokens em logs.

Não confiar em identidade fornecida pelo cliente sem validação adequada.

---

# 22. AUTORIZAÇÃO

Autenticação responde quem é o usuário.

Autorização responde o que ele pode fazer.

Toda operação protegida deve verificar autorização no lado confiável do sistema.

Não usar somente:

- esconder botão;
- rota frontend;
- flag visual;

como mecanismo de autorização.

---

# 23. MULTI-TENANCY

Produtos multi-tenant devem possuir isolamento explícito.

Toda consulta sensível deve considerar tenant correto.

Evitar filtros de tenancy dispersos e fáceis de esquecer.

Quando possível, centralizar mecanismos de isolamento.

Acesso cross-tenant indevido é STOP condition.

---

# 24. DADOS

O modelo de dados deve preservar:

- integridade;
- ownership;
- consistência;
- rastreabilidade;
- tenancy;
- auditabilidade.

Regras importantes devem existir em camadas adequadas.

Quando apropriado, utilizar:

- constraints;
- foreign keys;
- unique indexes;
- checks;
- transações.

---

# 25. MIGRATIONS

Mudanças de schema devem usar migrations rastreáveis.

Toda migration relevante deve considerar:

- compatibilidade;
- volume;
- downtime;
- rollback;
- dados existentes;
- índices;
- locks;
- risco operacional.

Evitar migrations destrutivas sem plano.

Não remover coluna ou tabela em produção apenas porque aparentemente não é utilizada.

Confirmar consumidores.

---

# 26. OPERAÇÕES DESTRUTIVAS

Qualquer operação potencialmente destrutiva exige cuidado proporcional.

Antes de execução crítica, identificar:

- impacto;
- escopo;
- backup;
- rollback;
- autorização;
- evidências.

Operação destrutiva não autorizada é STOP condition.

---

# 27. TRANSAÇÕES

Utilizar transações quando múltiplas operações precisarem preservar atomicidade.

Não manter transações abertas por mais tempo que o necessário.

Considerar impacto de concorrência e locks.

---

# 28. CONCORRÊNCIA

Fluxos concorrentes devem considerar:

- race conditions;
- double submission;
- escrita concorrente;
- consistência;
- locks;
- optimistic concurrency;
- idempotência.

Nunca presumir execução exclusivamente sequencial quando o ambiente permite concorrência.

---

# 29. IDEMPOTÊNCIA

Operações sujeitas a retry devem considerar idempotência.

Especialmente:

- pagamentos;
- webhooks;
- criação de registros;
- jobs;
- integrações externas;
- comandos críticos.

Idempotência deve possuir estratégia explícita quando necessária.

---

# 30. CACHE

Cache deve existir por razão mensurável.

Definir:

- chave;
- TTL;
- invalidação;
- consistência;
- fallback.

Não usar cache como correção para arquitetura incorreta.

Não armazenar informação sensível sem proteção adequada.

---

# 31. FILAS E PROCESSAMENTO ASSÍNCRONO

Jobs assíncronos devem considerar:

- retry;
- idempotência;
- dead-letter;
- timeout;
- observabilidade;
- correlação;
- prioridade;
- falha parcial.

Um job não pode desaparecer silenciosamente.

---

# 32. INTEGRAÇÕES

Integrações externas devem ter boundary explícito.

Considerar:

- autenticação;
- autorização;
- timeout;
- retry;
- rate limit;
- idempotência;
- fallback;
- observabilidade;
- erros do provider;
- indisponibilidade.

---

# 33. MULTI-PROVIDER

Multi-provider deve ser utilizado quando houver benefício concreto.

Benefícios possíveis:

- reduzir lock-in;
- continuidade operacional;
- custo;
- cobertura;
- diferenças regionais;
- flexibilidade comercial.

Evitar abstração artificial quando somente um provider é necessário e troca futura não possui valor real.

Interfaces de provider devem representar capacidades do domínio, não copiar SDK externo cegamente.

---

# 34. FM COGNITIVE VERTICAL CORE

O FM Cognitive Vertical Core é parte da arquitetura dos produtos Nova FM quando aplicável.

Ele é o coordenador cognitivo-operacional do produto.

Responsabilidades possíveis:

- compreender contexto;
- interpretar intenção;
- coordenar capacidades;
- recomendar ações;
- selecionar especialistas;
- manter contexto operacional;
- apoiar decisões.

O Core não deve substituir componentes determinísticos em ações críticas.

---

# 35. CADEIA DE AUTORIDADE DO CORE

Para operações críticas:

Core/IA  
→ interpretação  
→ recomendação/intenção  
→ política ou contrato aprovado  
→ serviço determinístico autorizado  
→ validação  
→ execução  
→ auditoria

O Core não deve:

- executar transação financeira diretamente sem serviço autorizado;
- ignorar autorização;
- alterar dado crítico fora de contrato;
- substituir validações;
- decidir sozinho política sensível.

---

# 36. SERVIÇOS DETERMINÍSTICOS

Execuções críticas devem ser realizadas por serviços previsíveis.

Exemplos:

- persistência;
- autorização;
- cálculo financeiro;
- emissão fiscal;
- movimentação de saldo;
- provisionamento;
- exclusão;
- alteração de privilégios.

IA pode orientar.

O serviço autorizado executa.

---

# 37. SEGURANÇA POR CONSTRUÇÃO

Segurança deve existir durante a construção, não apenas no final.

Aplicar:

- least privilege;
- defense in depth;
- fail-closed quando aplicável;
- validação;
- autorização;
- isolamento;
- gestão segura de segredos;
- logs seguros;
- dependências atualizadas.

---

# 38. SEGREDOS

Nunca armazenar segredo em:

- código;
- repositório;
- commit;
- screenshot;
- log;
- documentação pública;
- frontend.

Utilizar mecanismo seguro de secrets.

Segredo exposto é STOP condition.

Se exposição ocorrer, considerar rotação.

---

# 39. INPUT VALIDATION

Toda entrada externa deve ser considerada não confiável.

Validar:

- tipo;
- formato;
- tamanho;
- domínio permitido;
- autorização;
- contexto.

Não depender apenas da validação do frontend.

---

# 40. FAIL-CLOSED

Quando falha de validação, autorização ou política impedir determinação segura, preferir negar operação a permitir silenciosamente.

Aplicar proporcionalmente ao risco.

---

# 41. TRATAMENTO DE ERROS

Erros devem ser:

- detectáveis;
- observáveis;
- classificáveis;
- compreensíveis para o sistema;
- seguros para o usuário.

Não vazar:

- stack trace;
- segredo;
- query;
- token;
- detalhes internos sensíveis.

---

# 42. LOGGING

Logs devem ajudar investigação.

Registrar, quando necessário:

- operação;
- resultado;
- contexto técnico;
- correlação;
- duração;
- erro.

Evitar registrar dados sensíveis.

Logs devem ser estruturados quando a plataforma permitir.

---

# 43. CORRELATION ID

Fluxos distribuídos devem considerar identificador de correlação.

Isso facilita rastrear:

frontend  
→ API  
→ serviço  
→ provider  
→ job

---

# 44. MÉTRICAS

Métricas devem refletir comportamento relevante.

Exemplos:

- latência;
- erros;
- throughput;
- fila;
- disponibilidade;
- consumo;
- sucesso de integrações.

Não criar métricas sem uso operacional.

---

# 45. TRACING

Tracing distribuído deve ser utilizado quando complexidade justificar.

Especialmente em sistemas com múltiplos serviços ou integrações.

---

# 46. HEALTH CHECKS

Serviços relevantes devem expor mecanismos adequados para monitoramento de saúde.

Evitar health check que retorna sucesso mesmo quando dependência crítica está indisponível.

---

# 47. TESTES

Testes devem ser proporcionais ao risco.

Nenhum tipo de teste é obrigatório universalmente.

Selecionar conjunto adequado entre:

- unitário;
- integração;
- contrato;
- E2E;
- regressão;
- segurança;
- performance;
- migration.

---

# 48. TESTES UNITÁRIOS

Priorizar em:

- regras de domínio;
- cálculos;
- transformações;
- validações complexas;
- componentes puros.

Evitar testar detalhes internos sem valor.

---

# 49. TESTES DE INTEGRAÇÃO

Utilizar quando comportamento depende de:

- banco;
- API;
- fila;
- storage;
- provider;
- autenticação.

Devem validar integração real ou suficientemente representativa.

---

# 50. TESTES DE CONTRATO

Contratos entre componentes devem ser protegidos quando mudança independente representar risco.

Especialmente:

- API;
- eventos;
- providers;
- schemas.

---

# 51. TESTES E2E

Utilizar para fluxos críticos do usuário.

E2E não deve substituir testes de níveis menores.

Manter conjunto enxuto e confiável.

---

# 52. TESTES DE REGRESSÃO

Toda correção relevante deve considerar teste que impeça retorno do defeito.

---

# 53. TESTES DE SEGURANÇA

Aplicar conforme risco.

Validar especialmente:

- autenticação;
- autorização;
- tenancy;
- dados sensíveis;
- inputs;
- privilégios;
- segredos.

---

# 54. TESTES DE PERFORMANCE

Executar quando houver requisito ou risco real de:

- escala;
- latência;
- concorrência;
- carga;
- volume de dados.

---

# 55. EVIDÊNCIA DE TESTE

Não declarar "testado" apenas porque código compila ou parece correto.

Registrar:

- comando;
- cenário;
- resultado;
- ambiente;
- limitações.

---

# 56. GIT

Git é parte da rastreabilidade técnica.

Mudanças devem preservar histórico compreensível.

Evitar grandes alterações não relacionadas no mesmo commit.

---

# 57. BRANCHES

Usar estratégia coerente com projeto.

Branches devem representar intenção quando possível.

Evitar branch permanente sem necessidade.

---

# 58. COMMITS

Commits devem ser:

- pequenos quando possível;
- coerentes;
- descritivos;
- reversíveis.

Evitar mensagens como:

`update`
`fix`
`changes`
`final`

quando não explicarem intenção.

---

# 59. PULL REQUESTS

PR deve permitir revisão eficiente.

Incluir quando aplicável:

- objetivo;
- contexto;
- alterações;
- testes;
- evidências;
- screenshots;
- migrations;
- riscos;
- pendências.

---

# 60. REVISÃO DE DIFF

Antes de entregar, revisar o próprio diff.

Verificar:

- arquivos inesperados;
- segredos;
- debug temporário;
- código morto;
- alteração de configuração;
- dependência acidental;
- formatação excessiva;
- regressão óbvia.

---

# 61. CÓDIGO GERADO POR IA

Código gerado por IA não recebe exceção.

Deve passar pelos mesmos padrões de:

- revisão;
- segurança;
- testes;
- evidência;
- rastreabilidade;
- documentação.

Não aceitar output de IA como correto por padrão.

---

# 62. CI

CI deve automatizar validações repetíveis.

Pode incluir:

- lint;
- typecheck;
- build;
- testes;
- migrations;
- segurança;
- análise estática.

Falha de CI não deve ser ignorada para declarar prontidão.

---

# 63. CD

Deploy automatizado deve possuir controles proporcionais ao ambiente.

Produção deve exigir evidências e gates aplicáveis.

---

# 64. AMBIENTES

Ambientes devem possuir finalidade clara.

Exemplos:

- desenvolvimento;
- preview;
- staging;
- produção.

Evitar dependência de ambiente local único.

---

# 65. CONFIGURAÇÃO

Configuração deve ser externa ao código quando apropriado.

Separar configuração de:

- dev;
- teste;
- staging;
- produção.

Não usar segredo como configuração versionada.

---

# 66. DEPLOY

Antes de deploy relevante verificar:

- build;
- testes;
- migrations;
- configuração;
- secrets;
- dependências;
- observabilidade;
- rollback.

---

# 67. ROLLBACK

Toda mudança de risco deve considerar como voltar.

Rollback pode envolver:

- versão anterior;
- feature flag;
- migration reversa;
- restauração;
- desativação de rota;
- fallback.

Não assumir que rollback de código reverte automaticamente schema ou dados.

---

# 68. FEATURE FLAGS

Utilizar quando ajudarem em:

- rollout gradual;
- mitigação;
- teste;
- desligamento rápido;
- migração.

Flags temporárias devem possuir plano de remoção.

---

# 69. OBSERVABILIDADE

Sistema pronto não é apenas sistema que executa.

Também deve ser possível compreender:

- se está funcionando;
- quando falha;
- onde falha;
- qual impacto;
- qual operação foi afetada.

---

# 70. DOCUMENTAÇÃO

Documentação deve refletir o sistema real.

Atualizar quando aplicável:

- README;
- arquitetura;
- contratos;
- ADRs;
- setup;
- configuração;
- deploy;
- runbook;
- integração.

Não preservar documentação sabidamente incorreta como vigente.

---

# 71. RUNBOOKS

Operações críticas devem possuir instruções suficientes para diagnóstico e recuperação.

Especialmente:

- deploy;
- incidentes;
- migrations;
- providers;
- jobs;
- integrações críticas.

---

# 72. EVIDÊNCIAS

Afirmações técnicas relevantes devem possuir evidência.

Evidências possíveis:

- commit;
- diff;
- PR;
- workflow;
- teste;
- log;
- screenshot;
- configuração;
- documentação;
- resposta de serviço.

---

# 73. RASTREABILIDADE

Deve ser possível relacionar, quando aplicável:

requisito  
→ decisão  
→ implementação  
→ commit/PR  
→ teste  
→ evidência  
→ auditoria  
→ release

---

# 74. ESTADOS DE PRONTIDÃO

Os estados são distintos:

**IMPLEMENTADO**  
Código ou configuração existe.

**INTEGRADO**  
A mudança funciona conectada aos componentes necessários.

**TESTADO**  
Existem testes e evidências adequadas.

**HOMOLOGADO**  
Validação independente foi concluída conforme os gates.

**PRONTO PARA PRODUÇÃO**  
Todos os critérios técnicos e operacionais exigidos foram atendidos.

**COMERCIALMENTE DISPONÍVEL**  
Produto foi formalmente disponibilizado ao mercado.

Não pular semanticamente etapas.

---

# 75. DEFINITION OF DONE DO BUILDER

Uma unidade de trabalho somente pode sair do Builder quando, proporcionalmente ao escopo:

- CURRENT foi compreendido;
- escopo foi respeitado;
- implementação foi concluída;
- contratos estão coerentes;
- testes necessários foram executados;
- CI relevante foi verificado;
- documentação necessária foi atualizada;
- evidências foram reunidas;
- riscos conhecidos foram registrados;
- pendências foram declaradas;
- handoff foi preparado.

Isso não significa homologação.

---

# 76. GATES

Gates existem para impedir progressão sem evidência suficiente.

Um gate deve possuir:

- entrada;
- critérios;
- evidências;
- autoridade;
- saída.

Nunca declarar gate aprovado sem evidência.

---

# 77. STOP CONDITIONS

A execução deve parar e ser escalada quando houver evidência de:

- acesso cross-tenant;
- bypass de autenticação;
- bypass de autorização;
- escalada de privilégio;
- segredo exposto;
- vazamento de dados;
- risco de fraude;
- corrupção de dados;
- perda de dados;
- operação destrutiva não autorizada;
- vulnerabilidade crítica;
- conflito grave de autoridade;
- ausência de evidência essencial para mudança de alto risco.

STOP condition não significa pânico.

Significa que a continuação automática não é aceitável.

---

# 78. ANTI-PATTERNS PROIBIDOS

Evitar:

- implementar antes de entender CURRENT;
- reescrever sistema sem necessidade;
- esconder falha de CI;
- remover teste para fazer pipeline passar;
- colocar segredo no repositório;
- autorização somente no frontend;
- misturar tenant sem isolamento;
- alterar schema destrutivamente sem análise;
- adicionar provider diretamente ao domínio;
- declarar pronto sem evidência;
- apresentar TARGET como CURRENT;
- confiar cegamente em código de IA;
- corrigir sintoma ignorando causa;
- fazer deploy sem rollback quando risco exigir;
- produzir documentação fictícia;
- marcar tarefa como concluída com pendência crítica escondida.

---

# 79. CHECKLIST PRÉ-IMPLEMENTAÇÃO

Antes de iniciar:

[ ] Projeto correto confirmado  
[ ] Repositório correto confirmado  
[ ] Branch/PR correta confirmada  
[ ] CURRENT compreendido  
[ ] TARGET definido  
[ ] Escopo claro  
[ ] Dependências identificadas  
[ ] Riscos identificados  
[ ] STOP conditions verificadas  
[ ] System Design/ADR realizado quando necessário  
[ ] Estratégia de teste definida  
[ ] Estratégia de rollback considerada  

---

# 80. CHECKLIST DURANTE IMPLEMENTAÇÃO

[ ] Mudanças permanecem dentro do escopo  
[ ] Código segue padrões  
[ ] Segurança está sendo considerada  
[ ] Contratos permanecem coerentes  
[ ] Dados permanecem íntegros  
[ ] Tenancy permanece protegida  
[ ] Integrações tratam falhas  
[ ] Logs não expõem segredos  
[ ] Testes acompanham alterações relevantes  
[ ] Documentação necessária está sendo atualizada  

---

# 81. CHECKLIST PRÉ-HANDOFF

[ ] Diff revisado  
[ ] Nenhum segredo encontrado  
[ ] Nenhum debug temporário indevido  
[ ] Build verificado quando aplicável  
[ ] Typecheck verificado quando aplicável  
[ ] Testes relevantes executados  
[ ] CI verificado  
[ ] Migrations verificadas  
[ ] Riscos declarados  
[ ] Pendências declaradas  
[ ] Evidências reunidas  
[ ] Handoff preparado  

---

# 82. HANDOFF PARA FM AUDIT & FIX

Toda unidade de trabalho relevante deve chegar ao FM Audit & Fix com contexto suficiente para auditoria independente.

O handoff deve conter, quando aplicável:

**PROJETO**

**REPOSITÓRIO**

**BRANCH**

**PR**

**COMMIT**

**OBJETIVO**

**CURRENT ANTES DA MUDANÇA**

**ESCOPO**

**ALTERAÇÕES REALIZADAS**

**ARQUIVOS AFETADOS**

**SERVIÇOS AFETADOS**

**CONTRATOS ALTERADOS**

**DADOS/MIGRATIONS**

**DECISÕES/ADRs**

**TESTES EXECUTADOS**

**RESULTADOS**

**ESTADO DO CI**

**EVIDÊNCIAS**

**RISCOS CONHECIDOS**

**LIMITAÇÕES**

**PENDÊNCIAS**

**PASSOS DE REPRODUÇÃO**

**ITENS QUE EXIGEM AUDITORIA**

---

# 83. RELAÇÃO COM FM AUDIT & FIX

O Builder não deve auditar a si próprio como autoridade final.

O FM Audit & Fix é responsável por realizar revisão independente.

O Audit & Fix pode:

- aprovar tecnicamente;
- solicitar evidência;
- devolver para correção;
- identificar risco;
- corrigir falha autorizada;
- bloquear progressão em STOP condition.

O Builder deve responder às constatações com evidência e correções, não com justificativas vagas.

---

# 84. RELAÇÃO COM FM PREMIUM UX/UI

O Builder entrega produto funcional e tecnicamente consistente.

O FM Premium UX/UI atua sobre:

- experiência;
- consistência visual;
- design system;
- acessibilidade aprofundada;
- responsividade;
- microinterações;
- qualidade percebida;
- refinamento comercial.

Mudanças visuais não devem quebrar contratos, regras ou segurança.

Após etapa visual relevante, o produto retorna ao Audit & Fix para validação final.

---

# 85. ESTEIRA OFICIAL

Fluxo padrão:

BRIEFING / CURRENT  
→ FM SaaS Builder  
→ FM Audit & Fix  
→ FM Premium UX/UI  
→ FM Audit & Fix — validação final  
→ RELEASE

Nem toda tarefa exige todas as etapas.

Porém mudanças destinadas à produção devem possuir validação independente proporcional ao risco.

---

# 86. PRINCÍPIO FINAL

A Nova FM Tecnologia não mede qualidade pela quantidade de código produzido.

Qualidade significa entregar software que:

- resolve o problema correto;
- representa o CURRENT real;
- evolui para o TARGET aprovado;
- possui arquitetura compreensível;
- funciona de forma verificável;
- protege dados e usuários;
- pode ser mantido;
- pode ser auditado;
- pode ser operado;
- pode evoluir sem recomeçar do zero.

O FM SaaS Builder existe para construir com velocidade sem sacrificar disciplina.

---

# FIM DO DOCUMENTO
