# WP-R02-04 — Ledger comercial persistente

**Status:** PARTIAL — fundação interna; não ativada no produto.
**Base:** main@1586ec120ea8d5ee0a06a9ec704f3719f4cd4254; PR #48.
**Autoridade:** política V1 aprovada pelo Diretor em 15/10/2026; registro no documento da proposta.

## CURRENT, objetivo e fronteira

CostLedger contabiliza custo interno em memória; não é franquia contratada. Não existe
medição comercial durável no CURRENT. As telas de planos/trial/histórico/fatura das PRs
#45–#47 são preservadas. Este bloco acrescenta o journal comercial à persistência F3
existente, sem criar outro banco, gateway, autenticação ou agendador.

O domínio recebe snapshot imutável de ciclo pago/trial, pesos e preço versionados. O adapter
usa a transação F3 e lock por tenant, inclusive entre ciclos, para validar e anexar uma decisão.
A nova tabela credit_journal guarda OPEN, CONSENT, RESERVE, SETTLE, RELEASE e REVERSE.
UPDATE/DELETE são rejeitados pelo banco; replay retorna o lançamento existente. Uma reversão
é outro lançamento, com referência explícita, e nunca apaga a entrega original.

Não existe endpoint de mutação de consumo ou consentimento neste bloco. O browser não pode
informar quanto consumiu. Não há concessão automática de trial/quota, catálogo ativo ou
mudança nos entitlements existentes. O serviço só será ligado às rotas após o próximo bloco
provar a atomicidade da entrega, autorização, consentimento e UX de confirmação de débito.

## Invariantes e falhas

- Tenant explícito em toda leitura/mutação; consulta no banco filtrada por tenant.
- Operação lógica única por tenant mesmo na mudança de ciclo; troca de ação/ciclo no replay falha.
- Reserva integral consome disponibilidade, nunca receita/consumo realizado. Reserva incerta
  permanece pendente após restart; não expira nem inicia automaticamente outra chamada externa.
- CreditDecision.replayed impede interpretar replay como autorização de nova execução.
  Replay de reserva já concluída informa o estado terminal, não uma nova reserva.
- Liquidar só uma reserva e uma referência de entrega atômica única. Pacotes deverão ser
  representados pelas ações filhas, sem operação adicional de pacote. Falhas conhecidas
  liberam; política/output inválido não deve chegar à liquidação.
- Excedente desativado inicialmente; teto monetário exato em Decimal, considerando todas
  as reservas. Trial rejeita excedente. Revogar impede novas reservas adicionais sem apagar
  compromissos já autorizados. O ciclo seguinte não recebe saldo ou teto por acidente.
- Consentimento tem ator/referência/versão/preço/ciclo; autenticação OWNER/FINANCE e step-up
  são responsabilidade do serviço HTTP futuro. Persistência de adesão entre ciclos também
  será ligada à assinatura, sem inferir consentimento a partir do teto anterior.
- Reservar apenas em [início, fim); reconciliação posterior liquida o ciclo original.
  Fechamento/faturas e ajustes posteriores ao fechamento pertencem ao próximo bloco.

## Integração seguinte obrigatória

1. Autoridade de ciclo por aniversário e ativação por pagamento confirmado; snapshot a partir
   da assinatura, sem aceitar termos ou saldo arbitrários do cliente. Conversão trial/pago,
   carência, cancelamento e janela de uso precisam ser resolvidos por essa autoridade.
2. Commit da reserva ANTES da chamada IA. Não aninhar execução externa na transação HTTP
   atual: rollback poderia apagar a reserva após custo já realizado.
3. Identidade estável da execução, resultado durável recuperável e validação/policy antes
   de disponibilizar/liquidar, com vínculo atômico à entrega. Falha incerta exige reconciliação.
4. API/Web de leitura e consentimento, alertas 80/100%, confirmação prévia de débito e gates
   dos recursos ainda incompletos. Não substituir consumo indisponível por zero fictício.
5. Scheduler único e fatura com base seguinte + excedente anterior fechado; reversões tardias
   geram ajustes rastreáveis, sem alterar fatura paga. Não usar contador enviado pelo browser.

Essas são pendências de wiring, não uma certificação antecipada de F5/G5. O ledger interno
carrega o histórico completo do tenant a cada decisão; requer medição/compactação verificável
antes de volume comercial elevado.

## Migration, compatibilidade e rollback

005 é aditiva, destinada somente aos bancos descartáveis de teste/CI neste bloco. AppState
não instancia o adapter, portanto startup/rotas preservam compatibilidade com schema 004.
A versão anterior pode continuar rodando sem ler a tabela adicional. Não executar o down
em base com uso real: elimina evidência financeira; exportação/backup e autorização específica
são necessários. Rollback de código pode manter a tabela. Nenhuma migration externa,
religamento Cloud SQL, credencial, deploy ou pagamento faz parte deste bloco.

## Validação e handoff

Testes focados cobrem reserva/entrega/replay/restart, reserva incerta, falha/liberação,
reversão, teto/revogação, trial, isolamento, conflitos, fronteira de ciclo, concorrência,
rollback e imutabilidade física. A suíte PostgreSQL acrescenta workers independentes,
liquidação concorrente única, isolamento e UPDATE/DELETE rejeitados, além de up/down/up.
Resultados efetivamente executados e HEAD serão registrados na PR; CI PostgreSQL permanece
gate obrigatório antes de integração. Revisão independente financeira/segurança e
homologação externa continuam pendentes; este documento não aprova produção.

### Execução local em 15/10/2026

- Domínio: `python -m unittest discover -s tests -q` — 409 passaram.
- API: `python -m unittest discover -s tests_api -t . -q` — 331 executados,
  18 PostgreSQL ignorados por ausência de DSN; os demais passaram.
- Web: `npm test -- --run` — 89 passaram em 23 arquivos.
- `git diff --check` — passou.

Comandos Python executados no venv descartável, com dependências de backend/requirements.txt.
Resultados locais não substituem o job PostgreSQL 16 e demais gates da CI no commit da PR.
