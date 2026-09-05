# EVIDÊNCIA — Correção da P-19 (lacuna de mapeamento HTTP no Connector Hub)

**Data:** 04/09/2026
**Autor:** Assistente (Claude), sob supervisão do Diretor Fábio Aluizio da Silva
**Projeto:** CAMPAIA — F&M Tecnologia

---

## 1. Autorização do Diretor

Após o fechamento do B10 (catálogo de erros em linguagem de usuário), foi apresentada ao Diretor a constatação de que 3 dos 10 códigos de `ConnectorErrorCode` não tinham mapeamento HTTP em `STATUS_BY_CODE`, com uma recomendação marcada de engenharia sênior para corrigir.

O Diretor respondeu, em mensagem literal:

> **"pode corrigir não vamos deixar nenhum erro para trás"**

Esta instrução autorizou (a) a correção do código, (b) a exigência de prova real (não apenas "nada quebrou"), e (c) — por força do próprio enunciado "não vamos deixar nenhum erro para trás" — a atualização do catálogo B10 para não descrever como pendente algo que passou a estar corrigido.

---

## 2. Linha de base estabelecida antes de qualquer alteração

Antes de tocar em qualquer código, foi restaurada localmente uma cópia completa do backend (48 arquivos: `campaia_core/` 18, `api/` 16, `tests/` 9, `tests_api/` 5) a partir do Google Drive, usando um agente delegado para o trabalho mecânico de download.

**Divulgação de transparência:** o agente delegado, interrompido por um rate limit no meio da tarefa, inicialmente relatou de forma confusa. Ao ser cobrado por um relatório preciso e não otimista, o próprio agente revelou que 10 dos 48 arquivos — apesar de reportados como "prontos" antes da interrupção — ainda estavam byte-incorretos (truncados por escritas de uma reinicialização de contexto anterior que nunca haviam sido de fato verificadas por byte). Isso confirma a necessidade da disciplina do projeto de nunca aceitar "concluído" de um agente sem reverificação independente. Os 10 arquivos foram corrigidos pelo agente usando exclusivamente decodificação programática (nunca redigitação manual), e o resultado final foi reverificado.

Após a correção, os dois suites de teste foram executados **por mim, diretamente, via minha própria ferramenta de shell** — não apenas aceitando o relatório do agente:

```
$ python3 -m unittest discover -s tests
Ran 237 tests in 0.094s
OK

$ python3 -m unittest discover -s tests_api -t .
Ran 72 tests in ...s
OK
```

Baseline confirmada de forma independente: **237 + 72 = 309 testes, 100% passando**, antes de qualquer alteração de código.

**Anomalia documentada, não relacionada à P-19:** `api/routes_approvals.py` apresenta uma discrepância de 1 byte entre o metadado do Drive (`fileSize: 6588`) e o conteúdo real decodificado (6587 bytes, confirmado por dois downloads independentes byte-idênticos entre si, conteúdo puramente ASCII, terminando em exatamente uma quebra de linha). Foi investigada, tratada como anomalia de exportação do Drive externa a este trabalho, e deixada **sem alteração** — este arquivo não foi tocado pela correção da P-19.

---

## 3. A lacuna (P-19)

`campaia_core/connectors.py` define `ConnectorErrorCode` com 10 valores: `AUTH_EXPIRED`, `PERMISSION_DENIED`, `CAPABILITY_UNSUPPORTED`, `RATE_LIMITED`, `QUOTA_EXHAUSTED`, `VALIDATION_REJECTED`, `POLICY_VIOLATION`, `PARTIAL_FAILURE`, `TRANSIENT`, `UNKNOWN`.

`api/errors.py` mantém `STATUS_BY_CODE`, um dicionário que `from_domain_error()` consulta para traduzir qualquer `CampaiaError`/`ConnectorError` em uma resposta HTTP. Antes da correção, 3 desses 10 códigos não tinham entrada: `AUTH_EXPIRED`, `VALIDATION_REJECTED`, `PARTIAL_FAILURE`. Sem entrada, `from_domain_error()` colapsava silenciosamente qualquer um deles para `UNKNOWN`/500.

Isso não era uma lacuna teórica: `campaia_core/saga.py`, em `PublicationSaga._publish_channel` (linha ~191), efetivamente atribui `ConnectorErrorCode.VALIDATION_REJECTED` quando uma plataforma externa rejeita o conteúdo publicado — um caminho de código real, hoje.

---

## 4. Correção aplicada

Arquivo alterado: `api/errors.py`. Diff aplicado (inserção em `STATUS_BY_CODE`, após o bloco de comentário existente sobre `DenialCode`):

```python
    # campaia_core.connectors.ConnectorErrorCode values not previously mapped here
    # (P-19, found 2026-09-03 while building the user-facing error catalog). Without
    # these, from_domain_error() below silently collapsed all three to UNKNOWN/500,
    # even though VALIDATION_REJECTED is genuinely raised today (campaia_core/saga.py,
    # PublicationSaga._publish_channel) and simulator.py can script any of the ten
    # ConnectorErrorCode values as a scripted failure. AUTH_EXPIRED mirrors
    # UNAUTHENTICATED: the platform-side credential is no longer valid, not ours.
    # VALIDATION_REJECTED mirrors VALIDATION_FAILED: the external platform rejected the
    # submitted content/config. PARTIAL_FAILURE uses 207 Multi-Status because it is
    # genuinely a mixed outcome (some channels published, some did not), not a full
    # failure -- collapsing it to 422 would misrepresent a partial success as an error.
    "AUTH_EXPIRED": 401,
    "VALIDATION_REJECTED": 422,
    "PARTIAL_FAILURE": 207,
```

Racional de cada status, resolvendo a pergunta em aberto do catálogo original ("207 ou 422, a decidir" para `PARTIAL_FAILURE`):

| Código | HTTP | Por quê |
|---|---|---|
| `AUTH_EXPIRED` | 401 | Espelha `UNAUTHENTICATED`: a credencial do lado da plataforma externa não é mais válida — não é uma falha nossa. |
| `VALIDATION_REJECTED` | 422 | Espelha `VALIDATION_FAILED`: a plataforma externa rejeitou o conteúdo/configuração enviado. |
| `PARTIAL_FAILURE` | 207 (Multi-Status) | Decidido em vez de 422 porque é genuinamente um resultado misto (parte dos canais publicou, parte não) — não uma falha total. Usar 422 misrepresentaria um sucesso parcial como um erro puro. |

Tamanho do arquivo: 3500 bytes (original, confirmado igual ao Drive antes da edição) → **4509 bytes** (após a edição).

---

## 5. Prova real da correção (não apenas ausência de regressão)

Foi criado `tests_api/test_errors_p19.py` (novo arquivo, 3718 bytes) com 8 testes que provam a correção de ponta a ponta através de `from_domain_error()` — não apenas verificam o dicionário isoladamente:

1. `test_all_ten_connector_error_codes_are_mapped` — nenhum dos 10 códigos pode ficar de fora de `STATUS_BY_CODE`.
2. `test_auth_expired_maps_to_401`
3. `test_validation_rejected_maps_to_422`
4. `test_partial_failure_maps_to_207`
5. `test_from_domain_error_preserves_auth_expired_not_unknown` — prova via `from_domain_error()` real.
6. `test_from_domain_error_preserves_validation_rejected_not_unknown` — idem, citando explicitamente o caminho real em `saga.py`.
7. `test_from_domain_error_preserves_partial_failure_not_unknown` — idem.
8. `test_regression_before_fix_would_have_collapsed_to_unknown` — reproduz deliberadamente a lacuna antiga (removendo os 3 códigos de uma cópia do dicionário) e confirma que o mecanismo de colapso para `UNKNOWN` de fato ocorre sem a correção — prova que o problema original era real, não hipotético.

### Resultado da re-execução completa das suítes, após a correção

```
$ python3 -m unittest discover -s tests
Ran 237 tests in 0.094s
OK

$ python3 -m unittest discover -s tests_api -t .
Ran 80 tests in 0.715s
OK
```

**237 (domínio, inalterado) + 80 (API/persistência: 72 preexistentes + 8 novas da P-19) = 317 testes, 100% passando, zero regressão.**

Estes números foram confirmados por mim diretamente nesta sessão, via minha própria ferramenta de shell, imediatamente antes da redação deste documento — não apenas aceitos de um relato anterior.

---

## 6. Documentação mantida em sincronia com o código (conforme "não vamos deixar nenhum erro para trás")

O catálogo `docs/09_CATALOGO_ERROS_USUARIO.md` foi atualizado (não deixado descrevendo uma lacuna já corrigida):

- Versão: `1.0.0` (29/08/2026) → **`1.1.0`** (04/09/2026), com nota explícita da correção da P-19 sob autorização do Diretor.
- Contagem de códigos ativos: 18 → **21** (3 novas linhas na tabela de mensagens: `AUTH_EXPIRED`, `VALIDATION_REJECTED`, `PARTIAL_FAILURE`, com título amigável, causa provável e ação sugerida ao usuário).
- Seção 2: os 10 valores de `ConnectorErrorCode` agora descritos como 100% cobertos.
- Seção 3: renomeada para "Achado e correção: 3 códigos do Connector Hub sem mapeamento HTTP (P-19)", reestruturada em "Achado (29/08/2026)" + "Correção (04/09/2026)", citando os 8 novos testes e os números exatos de re-execução (237+80).
- Seção 4 e Resumo: atualizados para refletir a lacuna como corrigida em código, não mais como constatação pendente.

Tamanho final: **14668 bytes** (anteriormente 12603 bytes na versão 1.0.0).

---

## 7. Uploads ao Google Drive (todos verificados por byte, primeira tentativa)

Todos os uploads seguiram a disciplina do projeto: para arquivos existentes, trash do arquivo antigo seguido de criação de um novo (nunca edição in-place); `base64Content` gerado programaticamente a partir do arquivo local real (nunca redigitação manual) e lido de volta via ferramenta `Read` antes do envio — lição aplicada desde o erro de transcrição ocorrido no upload do B10 em 03/09/2026.

| Arquivo | Pasta Drive | Ação | fileId antigo (trashed) | fileId novo | Bytes local | Bytes Drive | Verificado |
|---|---|---|---|---|---|---|---|
| `api/errors.py` | `api/` (`1uYWRfiT5xiRegazwIoRMBG_mPkodfk0n`) | trash+create | `1N0MT1LTfc6oaw4rNlCxAHg96kz2EiqiU` | `1u8v6N0V1WRrKPXe05W2v0JiEJXImtpJv` | 4509 | 4509 | ✅ |
| `tests_api/test_errors_p19.py` | `tests_api/` (`1TqhOFH7Aoza98lcm_8rMZbOQhdJMwp0a`) | create (novo) | — | `1MU2zqOF7NtyuEhG2bIMDB79YPFZttOuR` | 3718 | 3718 | ✅ |
| `docs/09_CATALOGO_ERROS_USUARIO.md` | `docs/` (`1ZpfJFspuO7L-nSQ7sUdvQKN8WZZ1g8_x`) | trash+create | `1spGTinX6n-SOULBFFala-vPYRpC7VEGc` | `14bc0ZHGYJp1JLODwsf9Aso5lFMGtfZWu` | 14668 | 14668 | ✅ |

Todos os três uploads casaram exatamente na primeira tentativa (nenhuma correção necessária), diferentemente do upload do catálogo B10 em 03/09/2026 (que exigiu uma segunda tentativa por um erro de transcrição meu, já documentado em `EVIDENCIA_B10_CATALOGO_ERROS_20260903.md`).

Todos os uploads usaram `contentMimeType: "text/plain"` e `disableConversionToGoogleType: true`, conforme exigido pelo projeto para preservar o conteúdo exato sem conversão para formato Google.

---

## 8. Resumo de fechamento

- **Lacuna:** 3 de 10 códigos de `ConnectorErrorCode` (`AUTH_EXPIRED`, `VALIDATION_REJECTED`, `PARTIAL_FAILURE`) colapsavam silenciosamente para `UNKNOWN`/500.
- **Autorização:** Diretor, literal — "pode corrigir não vamos deixar nenhum erro para trás".
- **Correção:** 3 entradas adicionadas a `STATUS_BY_CODE` em `api/errors.py`, com racional documentado para cada status HTTP escolhido.
- **Prova:** 8 novos testes, incluindo um teste de regressão que reproduz deliberadamente a lacuna antiga para confirmar que o mecanismo de colapso era real.
- **Suítes completas:** 237 (domínio) + 80 (API/persistência) = **317 testes, 100% passando, zero regressão** — confirmado por execução direta, não por relato de terceiros.
- **Documentação:** catálogo B10 atualizado para v1.1.0, sem deixar a lacuna descrita como pendente.
- **Uploads:** 3 arquivos enviados ao Drive, todos byte-verificados, primeira tentativa.
- **Anomalia não relacionada, documentada e não corrigida:** discrepância de 1 byte em `api/routes_approvals.py` (metadado do Drive vs. conteúdo real), root-caused como anomalia externa de exportação, sem impacto funcional, fora do escopo desta correção.

---

*Este documento é evidência primária, persistida no Google Drive, do fechamento da P-19 conforme a instrução literal do Diretor.*
