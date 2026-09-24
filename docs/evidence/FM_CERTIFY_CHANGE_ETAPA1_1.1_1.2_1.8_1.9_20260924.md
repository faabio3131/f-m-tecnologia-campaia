# fm-certify-change — Etapa 1 do cronograma mestre (itens 1.1, 1.2, 1.8, 1.9)

**Data:** 24/09/2026 · **Repositório:** `faabio3131/f-m-tecnologia-campaia` · **Branch:**
`main` · **HEAD certificado:** `8fb3cbfbaf3f6208983d44092dc9c0e56766ad53` (PR #18, mesclado
nesta sessão) · **Worktree:** limpo (`git status` sem alterações pendentes).

## Baseline

- `CLAUDE.md` e os documentos mestres da Nova FM já haviam sido lidos no início da sessão
  (Prompt 1). Reconfirmado: exceção de merge pré-autorizado pelo Diretor (24/09/2026) —
  merge liberado quando a suíte completa estiver 100% verde, executada de fato nesta sessão,
  no HEAD exato do PR. Não dispensa `fm-security-review`, ADR, ou STOP conditions.
- HEAD confirmado por execução direta (`git rev-parse HEAD`, `git branch --show-current`),
  não presumido.
- Escopo certificado: os 3 PRs mesclados nesta sessão dentro da Etapa 1 —
  - PR #17 (`e034e22`) — itens 1.1 (dedupe do webhook persistido) e 1.2 (rate limiting).
  - PR #18 (`8fb3cbf`) — item 1.9 (fm-security-review formal, achado de escopo de unidade
    de negócio corrigido).
  - Este próprio documento — item 1.8 (esta certificação).

## Gates executados neste HEAD

| Gate | Comando | Resultado |
|---|---|---|
| Testes de domínio | `python3 -m unittest discover -s tests` (em `backend/`) | **343 testes, OK** |
| Testes de API/BFF | `python3 -m unittest discover -s tests_api -t .` (em `backend/`) | **105 testes, OK** |
| Validação de contrato AsyncAPI | `python3 validate_events_asyncapi.py` (em `contracts/`) | **OK — 24 eventos verificados de ponta a ponta** |
| Auditoria de diff (debug residual/secrets) | `git diff 4c30bba..HEAD -- backend` grepado contra `print(`, `pdb.set_trace`, `TODO`, `FIXME`, credenciais hardcoded | **Nenhuma ocorrência** |
| CI (GitHub Actions, `CAMPAIA Backend Tests`) | `actions_list`/`actions_get` sobre o run do HEAD atual | **`failure`, ver nota abaixo — não bloqueante nesta certificação** |

### Nota sobre o gate de CI

O workflow `CAMPAIA Backend Tests` está com `conclusion: failure` no HEAD atual
(`8fb3cbf`, run #74) — mas **também está `failure` em TODOS os últimos 10 runs de `main`
verificados**, remontando a commits completamente não relacionados a este trabalho
(ex.: run #56, `Fix: Asaas requires cpfCnpj...`, e run #58, #60, #62, #64, #66, #68, #70,
#72), inclusive commits que já foram certificados e mesclados em sessões anteriores sob a
mesma exceção do Diretor. Todos os runs falham em 2 a 4 segundos — tempo incompatível com
`pip install` + suíte real rodando (isso levaria minutos), o que é evidência de uma falha de
infraestrutura do runner/CI (ex. billing/quota do GitHub Actions para esta conta), não uma
falha real de teste. Tentativa de baixar o log bruto do run falhou por bloqueio de rede do
proxy deste ambiente (não consigo confirmar a causa raiz exata do lado do GitHub a partir
daqui). Como os mesmos testes rodam 100% verdes localmente, no HEAD exato, nesta sessão
(343 + 105), e a exceção registrada em `CLAUDE.md` (24/09/2026) cobre exatamente este caso —
suíte 100% verde executada de fato, nesta sessão, no HEAD exato —, este gate de CI é tratado
como **pendência não bloqueante, registrada explicitamente, não escondida**, e não como
"verde" (não afirmo isso). Recomendação registrada para o Diretor: investigar
diretamente no GitHub (Settings → Billing/Actions, ou Settings → Actions → Runners) por que
todo run de `main` falha em segundos — está fora do que esta sessão consegue diagnosticar
sem acesso à interface de billing do GitHub.

## Achados de segurança cobertos nesta Etapa

- Item 1.1 e 1.2: ver `docs/evidence/EVIDENCIA_ETAPA1_1.1_1.2_20260924.md`.
- Item 1.9: ver `docs/evidence/FM_SECURITY_REVIEW_BACKEND_FULL_20260924.md` — um achado real
  (escopo de unidade de negócio não aplicado na camada HTTP) corrigido, testado e
  documentado nesta mesma sessão; dois itens registrados e conscientemente não corrigidos
  agora (autenticação de desenvolvimento — item 1.3, decisão do Diretor; duas rotas mutantes
  sem idempotency-key — impacto baixo, sem efeito externo real).
- Nenhum achado desta Etapa é `STOP DE PRODUÇÃO` no estado atual (ambiente de
  desenvolvimento, nenhum tenant real, nenhuma unidade de negócio múltipla em uso).

## Veredito

**CERTIFICADO COM PENDÊNCIAS NÃO BLOQUEANTES**

Todos os gates obrigatórios que esta sessão consegue executar diretamente (testes de
domínio, testes de API, validação de contrato AsyncAPI, auditoria de diff) estão
comprovadamente verdes no HEAD `8fb3cbf`. A única pendência é o gate de CI do GitHub
Actions, que está vermelho por um motivo de infraestrutura pré-existente e não relacionado a
este trabalho (confirmado por 10 runs consecutivos falhando em segundos, incluindo commits
anteriores já certificados) — registrado explicitamente acima, não somado como verde, e
citado como a exceção do Diretor que especificamente cobre este cenário (suíte 100% verde
executada de fato nesta sessão, no HEAD exato, é o critério de pré-autorização de merge —
já usado para mesclar os PRs #17 e #18 nesta mesma sessão).

## Estado

- **Item 1.1 (dedupe persistido):** TESTADO.
- **Item 1.2 (rate limiting):** TESTADO.
- **Item 1.8 (esta certificação):** CONCLUÍDA — veredito acima.
- **Item 1.9 (security review completo):** TESTADO, achado corrigido e testado.
- Etapa 1 como um todo: **INTEGRADO** e **TESTADO** para os itens 1.1, 1.2, 1.8, 1.9.
  **NÃO** `PRONTO PARA PRODUÇÃO` nem `COMERCIALMENTE DISPONÍVEL` — os itens 1.3 (provedor
  de identidade real), 1.5 (preços dos planos), 1.6 (autorização para provisionar nuvem) e
  1.7 (conta Asaas de produção) do cronograma mestre continuam pendentes de decisão do
  Diretor, conforme o próprio cronograma já registra, e nenhum deles foi decidido ou
  presumido nesta sessão.

## Confirmação de merge/deploy

Nenhum novo merge ocorreu como parte desta certificação (os PRs #17 e #18 já haviam sido
mesclados antes desta certificação começar, sob a mesma exceção). Nenhum deploy, release ou
alteração de produção ocorreu ou foi solicitado.
