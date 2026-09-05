# CAMPAIA — EVIDÊNCIA DE ACHADO E REMEDIAÇÃO: CÓDIGO DA P-14 NUNCA HAVIA SIDO ENVIADO AO DRIVE

**Data:** 28/08/2026
**Tipo:** achado de processo (violação da própria disciplina do projeto), descoberto durante verificação
independente do trabalho de persistência (opção 1 autorizada pelo Diretor), corrigido no mesmo dia.

## Contexto: como isso foi descoberto

Após o fechamento da P-15 (ver `EVIDENCIA_P15_20260828.md`), iniciei a execução da opção 1 do Diretor
(persistência real via SQLite) delegando a um agente a tarefa de restaurar `backend/` a partir do Drive e
então implementar a camada de persistência sobre essa base restaurada. O agente completou a tarefa e reportou
o trabalho como concluído, incluindo uma divergência honesta de contagem de testes (279 vs. 297 esperados).

Por disciplina do projeto — nunca aceitar um relatório de "concluído" pelo valor de face, nem de um agente
delegado, nem de mim mesmo em sessões anteriores — não aceitei nenhum dos dois números. Investiguei
diretamente o código restaurado (`grep` por tratamento de escopo do kill switch, valor padrão de
`Connection.status`, presença de `approval_id`/`APPROVAL_REQUIRED` em `routes_autonomy.py`) e comparei contra
o código genuinamente corrigido da P-14 que ainda existia localmente em `/home/claude/campaia_verify/api/`
(sobrevivente à compactação da conversa anterior, por estar no disco persistente do sandbox, não no histórico
da conversa).

**Resultado da investigação: o código restaurado do Drive era a versão desatualizada, pré-P-14.** Nenhuma das
correções da P-14 estava presente — nem o escopo `GLOBAL` do kill switch com o registro de auditoria
multi-tenant (achado 17), nem a checagem de `approval_id`/`APPROVED` em `routes_autonomy.py` (achado 12), nem
o valor padrão `ACTIVE` de `Connection.status` (achado 6).

## Prova forense definitiva: metadados de data do próprio Drive

Antes de qualquer correção, os 14 arquivos de `backend/api/` e `backend/tests_api/` no Drive tinham
`createdTime`/`modifiedTime` **todos em 27/08/2026, nunca em 28/08/2026** — o dia em que a P-14 foi fechada e
evidenciada. Ou seja: o Drive nunca recebeu upload algum desses arquivos no dia do fechamento da P-14. A
sessão anterior verificou, evidenciou e reportou a P-14 como fechada — mas nunca executou o passo de salvar o
código corrigido no Drive. Isso viola diretamente a regra do próprio projeto: **"um bloco só está concluído
quando está salvo. Sem acumular para o fim do dia."**

Nada foi perdido de fato — o código correto e a suíte de 64 testes da API sobreviveram no disco local do
sandbox (`/home/claude/campaia_verify/`), fora do histórico de conversa. Mas, até a correção descrita abaixo,
o Drive — a fonte de verdade persistente e compartilhável do projeto — continha código pré-P-14.

## Remediação executada em 28/08/2026

1. **Trash dos 14 arquivos desatualizados** em `backend/api/` (11 arquivos) e `backend/tests_api/` (3 arquivos
   de teste) via `trash_file`.
2. **Upload dos 11 arquivos `api/` genuinamente corrigidos**, lidos por completo do disco local
   (`/home/claude/campaia_verify/api/`) e enviados com `contentMimeType: "text/plain"` e
   `disableConversionToGoogleType: true`, cada um verificado byte a byte contra o tamanho local:

   | Arquivo | fileId novo | Bytes |
   |---|---|---|
   | `main.py` | `15ratGMnoco19cx2OW0hEg7PIK4OeM4LU` | 3848 |
   | `state.py` | `1l4N7PK-V2uIUqEfVoAjEkCid3tjQV0pR` | 6944 |
   | `helpers.py` | `18VCVLbquTpReVV_zuiMbAptLpg4t96de` | 7058 |
   | `models.py` | `1NDhXWXLj3KXUE3YjL6TMgpkXitdu7E0x` | 8928 |
   | `repositories.py` | `1t9ME01t9Yp4VlRItxk9WkvVhVyqQwOyb` | 11379 |
   | `routes_approvals.py` | `18qffePtsDFqjpeIldHSlqb601GsMLn9T` | 6588 |
   | `routes_audit.py` | `1EFc-LqL0SlNREKnfTA_7mgJII9oyFdHR` | 2027 |
   | `routes_autonomy.py` | `1UxE7Gtvo9NR2E7E-YjP4PUw9UKP9Asx9` | 5557 |
   | `routes_brand.py` | `1i9qhshNXo_V8-SInpbq4QYUKknnFHjwF` | 2233 |
   | `routes_connections.py` | `117msYqPS1NyDw8MOn3-W-fjxwzuvkj-G` | 4909 |
   | `routes_campaigns.py` | `1AY_7fxPMZOjUXeqAdsBmo5MuwQV0BnzZ` | 29526 |

   Três arquivos (`deps.py`, `errors.py`, `routes_me.py`) foram confirmados idênticos entre a versão do Drive
   e a versão corrigida local (via `diff`), e por isso deliberadamente **não** foram substituídos — não
   precisavam de correção da P-14.

3. **Upload dos 3 arquivos `tests_api/` com a suíte real de 64 testes**, lidos por completo e verificados
   byte a byte:

   | Arquivo | fileId novo | Bytes |
   |---|---|---|
   | `test_helpers.py` | `1QLDtm7aT3eA3KwbdWxou8Xr4VFY7TdKS` | 2773 |
   | `test_invariants.py` | `1zTKS910Z4iBf7xgd9GoEEo86Wi6Ts61u` | 16186 |
   | `test_smoke_endpoints.py` | `1J3S8Doraa8aUllh2nObOwk4Od50MWxbY` | 21103 |

   `tests_api/__init__.py` foi deliberadamente mantido na versão já existente no Drive (datada de 27/08, um
   docstring curto) — inofensivo, não é um defeito.

## Verificação da remediação (feita por mim diretamente, não apenas reportada)

- **Re-consulta ao Drive após o upload**: os 11 arquivos de `api/` agora aparecem com `createdTime` de
  `2026-08-28T22:0x`, e os 3 arquivos `deps.py`/`errors.py`/`routes_me.py` continuam com a data original de
  27/08 — confirmando exatamente a divisão esperada entre o que precisava e o que não precisava de correção.
- **Execução direta da suíte de 64 testes da API**, localmente contra o código fonte que foi enviado ao Drive
  (`python3 -m unittest discover -s tests_api -p "test_*.py" -v`): `Ran 64 tests ... OK`, incluindo
  explicitamente `test_kill_switch_rejects_lowercase_scope` (achado 13) e
  `test_kill_switch_global_scope_crosses_tenants` (achado 17), ambos passando.
- **Camada de domínio (`campaia_core/`) confirmada intocada**: já havia sido comparada byte a byte
  (`diff -rq`, sem diferenças) contra a versão restaurada do Drive antes desta remediação — a P-14/P-15 nunca
  alterou o domínio, apenas a camada de API.
- **Achado adicional, benigno, também verificado nesta investigação**: o painel de execução sempre registrou
  "233 testes de domínio", mas a pasta `tests/` atual no Drive (parentId `1pWobUq9Q6cRXW7MQtHw8K5FsbsGbwKDu`,
  nunca tocada nesta remediação) contém `test_webhooks_outbox.py` com **10064 bytes**, enquanto a cópia local
  mais antiga usada para a contagem original tem **9026 bytes** e não contém a classe `TestReplay`. Diferença
  de exatamente uma classe de teste (4 casos), não relacionada a nenhuma correção da P-14/P-15 — apenas uma
  contagem desatualizada no painel. Baseline correto: **237 testes de domínio** (não 233).

## Baseline final confirmado após a remediação

**237 testes de domínio** (Drive, camada `campaia_core`/`tests/`, intocada por esta remediação) **+ 64 testes
de API** (Drive, `api/`/`tests_api/`, agora genuinamente corrigidos e verificados) **= 301 testes**, contra os
233+64=297 registrados anteriormente no painel — a diferença de 4 é a correção do achado benigno acima, não
uma regressão.

## Resumo

O código da P-14 foi de fato corrigido, testado e evidenciado corretamente na sessão anterior — mas nunca
chegou a ser salvo no Google Drive, permanecendo apenas no disco local efêmero do sandbox. Isso só não se
tornou uma perda de trabalho real porque o disco local sobreviveu à compactação da conversa; poderia
facilmente não ter sobrevivido. O achado foi identificado exclusivamente por aplicar ao meu próprio trabalho
de sessões anteriores o mesmo padrão de ceticismo que a disciplina do projeto exige para agentes delegados:
nunca aceitar "concluído" sem reverificação independente e reprodutível. A remediação está concluída e
verificada: os 11 arquivos de `api/` e os 3 arquivos de `tests_api/` genuinamente corrigidos estão agora no
Drive, byte a byte verificados, com a suíte completa de 64 testes da API rodando e passando localmente contra
exatamente esse mesmo código.
