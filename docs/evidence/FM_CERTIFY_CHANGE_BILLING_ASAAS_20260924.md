# fm-certify-change — motor de cobrança própria + gateway Asaas

**Data:** 24/09/2026 · **Repositório:** `faabio3131/f-m-tecnologia-campaia` (canônico, ADR-0015)
**Branch:** `main` · **HEAD certificado:** `3701db1d8f08f641eefea12f43e0e6640d11d0ef` (PR #12)
**Worktree:** limpo, `git status` confirmado sem alterações pendentes no momento da certificação
**Escopo certificado:** PRs #7, #8, #9, #10, #11, #12 (motor de cobrança, catálogo de planos,
adaptador Asaas, correções de fm-security-review) — tudo já mergeado em `main` neste HEAD.

## Baseline

1. `CLAUDE.md` lido nesta sessão antes de qualquer alteração no repositório canônico.
2. Critérios de aceite: 100% dos testes de domínio e de API verdes; contrato AsyncAPI válido;
   sem secret exposto; sem PII vazando em log/erro (gate adicionado nesta sessão via
   fm-security-review).
3. Todos os comandos abaixo foram reexecutados agora, neste HEAD exato — nenhum resultado de
   execução anterior foi reaproveitado sem reconfirmação.

## Certificação — comandos executados e resultado real

| Gate | Comando | Resultado |
|---|---|---|
| Testes de domínio | `cd backend && python3 -m unittest discover -s tests` | **321 aprovados**, 0 falhas |
| Testes de API/persistência | `cd backend && python3 -m unittest discover -s tests_api -t .` | **81 aprovados**, 0 falhas |
| Validação do contrato AsyncAPI | `cd contracts && python3 validate_events_asyncapi.py` | **`ALL CHECKS PASSED (24 events verified end-to-end)`** |
| CI do GitHub Actions (`backend-tests.yml`) | push automático no merge do PR #12 | **NÃO EXECUTADO DE FATO** — falha instantânea (~2s, `runner_id: 0`), mesma assinatura de cota de minutos da conta esgotada já diagnosticada nesta sessão em execuções anteriores. Não é falha de código: os mesmos comandos rodaram localmente, neste HEAD, com sucesso (linhas acima) |
| Lint / typecheck | — | **NÃO EXISTE** como gate oficial neste repositório (nenhum `pyproject.toml`/`.flake8`/`mypy.ini` configurado, nenhum passo de lint no workflow oficial) — não contado como pendência, porque não é um gate que este repositório define |
| Auditoria de diff (debug residual, secret, alteração não autorizada) | `grep` manual por `print(`/`TODO`/`FIXME`/`breakpoint()`/`pdb` nos 6 módulos do escopo | Nenhuma ocorrência real (o único `print(` encontrado está dentro de um comentário explicando a própria correção de segurança) |
| Sincronismo local/remoto | `git status`, `git log --oneline -1` | `main` local idêntico a `origin/main`, working tree limpo |
| fm-security-review | Execução formal nesta sessão | `docs/evidence/FM_SECURITY_REVIEW_BILLING_ASAAS_20260924.md` — 2 achados corrigidos, 2 achados registrados como bloqueadores de produção (não de certificação do estado atual) |

## Veredito

**`CERTIFICADO COM PENDÊNCIAS NÃO BLOQUEANTES`**

Pendências explícitas, nenhuma bloqueando a certificação deste HEAD para o estado atual
(desenvolvimento/Sandbox, sem exposição HTTP, sem produção):

1. **CI do GitHub Actions não executa** (cota de minutos da conta esgotada) — mitigado: os
   mesmos comandos que o CI rodaria foram executados localmente, neste HEAD exato, com
   sucesso. Não bloqueante porque a evidência equivalente existe; bloqueante seria declarar
   "CI verde" sem tê-lo executado, o que este documento não faz.
2. **Idempotência de cobrança só em memória** (achado #3 do fm-security-review) — não
   bloqueia o estado atual (nada em produção), mas **deve bloquear** qualquer uso real antes
   de ser corrigido.
3. **Ausência de webhook de confirmação de pagamento** (achado #5) — mesma natureza do item 2.
4. **Tabela real de preços dos planos ainda não definida** — `plan_catalog.py` pronto para
   recebê-la, mas nenhum arquivo de produção existe ainda (só o template de exemplo).
5. **Adaptador Asaas verificado uma única vez contra Sandbox real** (não repetido, não
   automatizado) — suficiente para certificar que o código funciona contra a API real, não
   suficiente para garantir que continuará funcionando sem verificação recorrente.

## Estado exato

**`TESTADO`** — unitariamente (321+81 testes automatizados) e por uma verificação manual
pontual contra a API real do Asaas Sandbox (`docs/evidence/VERIFICACAO_REAL_ASAAS_SANDBOX_20260924.md`).

**Não é** `INTEGRADO` (nenhuma rota HTTP em `api/` consome este motor ainda — decisão
deliberada, mesmo padrão do B5/pacing). **Não é** `HOMOLOGADO` (nenhum processo formal de
homologação/QA rodou). **Não é** `PRONTO PARA PRODUÇÃO` nem `COMERCIALMENTE DISPONÍVEL` — as
pendências 2–4 acima bloqueiam isso explicitamente.

## Confirmação de merge/deploy/produção

Todos os PRs deste escopo (#7–#12) **foram mergeados** em `main`, com autorização explícita do
Diretor a cada um (regra registrada no `CLAUDE.md`: merge pré-autorizado quando a suíte estiver
100% verde). **Nenhum deploy, release ou alteração de produção ocorreu** — este documento
certifica o estado do código no repositório, não uma implantação.
