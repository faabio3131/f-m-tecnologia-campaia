# CAMPAIA — O QUE SE CONSTRÓI AQUI E O QUE EXIGE PC

**Data:** 25/08/2026 · **Decisão do Diretor (D-07):** construir por aqui tudo que for possível; deixar para o
PC com VS Code apenas o que exigir máquina física.

---

## Regra de corte

Roda aqui: **Python puro, biblioteca padrão, sem rede, sem banco, sem build mobile.**
Exige PC: **qualquer coisa que precise instalar dependência, subir serviço, compilar app ou falar com a internet.**

---

## Bloco A — Já construído, com testes passando

| Item | Arquivo | Evidência |
|---|---|---|
| Máquina de estados com guardas | `campaia_core/states.py` | 8 testes |
| Autonomia e gatilhos de aprovação | `campaia_core/autonomy.py` | 6 testes |
| Budget Engine com reservas | `campaia_core/budget.py` | 8 testes |
| Policy Engine + `policy_decision_id` | `campaia_core/policy.py` | 9 testes |
| Idempotência e isolamento por tenant | `campaia_core/infra.py` | 3 testes |
| Capability Registry | `campaia_core/infra.py` | 5 testes |
| Contrato dos conectores + `SecretRef` | `campaia_core/connectors.py` | 7 testes |
| Provider Simulator com falhas | `campaia_core/simulator.py` | 2 testes |
| Saga multicanal com compensação | `campaia_core/saga.py` | 15 testes |
| Contratos (JSON Schema, OpenAPI) | `contracts/` | validados |
| Documentação, ADRs, threat model | `docs/` | — |

**Total:** 64 testes, 64 aprovados.

---

## Bloco B — Ainda dá para construir sem PC

Tudo abaixo é Python puro ou documento. Nenhum depende de PC, rede ou aprovação externa.

| # | Item | Por que cabe aqui |
|---|---|---|
| B1 | **Agentes especializados como funções puras** — contrato de entrada/saída, validação de schema, sanitizador que remove PII e credenciais antes de qualquer envio | O gateway de IA pode ser testado com um provedor falso, como o simulador de anúncios |
| B2 | **AI Gateway com provedor simulado** — seleção por tarefa, fallback registrado, teto de custo, proveniência, rejeição de saída fora do schema | Não precisa de chave de API para provar a lógica de governança |
| B3 | **Reconciliador** — detecção de divergência entre estado interno e plataforma, com o simulador alterando estado "por fora" | Puro domínio |
| B4 | **Outbox/Inbox e deduplicação de webhook** — verificação de assinatura com `hmac` da stdlib e proteção contra replay | `hmac` e `hashlib` são biblioteca padrão |
| B5 | **Motor de otimização** — detecção de desperdício, pacing de verba, proposta de ajuste sujeita à autonomia | Puro domínio |
| B6 | **Modelo de permissões RBAC/ABAC** com testes de autorização por papel, tenant e valor | Puro domínio |
| B7 | **DDL do PostgreSQL e migrations** — escritos e revisados aqui; executados no PC | SQL é texto |
| B8 | **Especificação de telas do app** — cada aba de configuração, com estados de loading, vazio, erro, sucesso e recuperação | Documento |
| B9 | **AsyncAPI do catálogo de eventos** | Documento |
| B10 | **Catálogo de erros voltado ao usuário** — mensagem compreensível por quem não é técnico, para cada código canônico | Documento |

Ordem sugerida: **B6 → B4 → B2 → B1 → B3 → B5 → B7 → B8 → B9 → B10.**
Permissões antes de tudo, porque atravessam todas as camadas.

---

## Bloco C — Exige PC com VS Code

Nada aqui é opcional; apenas fica para o fim.

| # | Item | O que exige |
|---|---|---|
| C1 | Repositório Git e CI | Máquina, conta no GitHub/GitLab |
| C2 | Instalar dependências (FastAPI, driver do Postgres, Temporal) | `pip install` com rede |
| C3 | Subir PostgreSQL e Redis | Docker |
| C4 | Executar migrations e testar RLS | Banco de verdade |
| C5 | Cofre de segredos | Serviço de nuvem |
| C6 | Aplicativo Flutter — build, emulador, Android e iOS | Flutter SDK; iOS exige macOS |
| C7 | Testes E2E e de carga | Ambiente completo |
| C8 | Adaptadores reais de Google, Meta e WhatsApp | Rede e credenciais |
| C9 | Sandbox e contas de teste | Contas nas plataformas |
| C10 | Teste com as contas do Diretor | Contas reais + autorização expressa |
| C11 | Publicação nas lojas e produção | Autorização expressa do Diretor |

---

## Como o Bloco A se conecta ao Bloco C

O núcleo construído aqui **não muda** quando o PC entrar. Ele não conhece rede, banco nem provedor. O que o
PC acrescenta é:

1. **Persistência:** trocar `IdempotencyStore` em memória por tabela com constraint de unicidade, e
   `BudgetEngine` em memória por linhas com bloqueio otimista. A lógica e os testes permanecem.
2. **Transporte:** o FastAPI expõe o OpenAPI já contratado, chamando este mesmo núcleo.
3. **Adaptadores reais:** implementam o mesmo contrato do `ProviderSimulator`. Trocar é configuração.

É por isso que valeu construir nesta ordem: o que foi feito aqui é justamente a parte que **não** se joga fora.

---

## Aviso operacional

O ambiente de trabalho é efêmero. Os arquivos precisam ser preservados no Drive e no projeto — senão a
próxima sessão começa sem o estado real, o que a Ordem Mestra proíbe no item 18.
