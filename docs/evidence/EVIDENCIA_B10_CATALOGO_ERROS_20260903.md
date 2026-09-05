# CAMPAIA — EVIDÊNCIA DE FECHAMENTO: B10 — CATÁLOGO DE ERROS EM LINGUAGEM DE USUÁRIO

**Data:** 03/09/2026
**Bloco:** B10, aprovado pelo Diretor com a resposta de uma palavra **"b10"**, em resposta à minha
recomendação marcada como engenheiro sênior entre as opções restantes de "opção 2" (B5/B7/B8/B10), após o
fechamento de B9 (AsyncAPI do catálogo de eventos — ver `docs/evidence/EVIDENCIA_B9_ASYNCAPI_20260829.md`).

## Contexto

Após reportar o fechamento de B9, apresentei ao Diretor uma recomendação clara para o próximo bloco entre
B5/B7/B8/B10 (seguindo sua instrução de processo permanente: "vc é o eng senior sempre de as opções com a
marcação de recomendo na melhor entre as opções"), recomendando B10 por ser o de menor dependência de
decisões de produto em aberto e menor risco de retrabalho. O Diretor aprovou com **"b10"**.

Antes de escrever qualquer mensagem, pesquisei a taxonomia real e atual de erros do CAMPAIA lendo diretamente
do Drive (não de memória ou de cache local desta sessão), seguindo a disciplina de "pesquisar primeiro"
already estabelecida no projeto.

## O que foi construído

Um documento (`docs/09_CATALOGO_ERROS_USUARIO.md`) que traduz os códigos técnicos de erro do CAMPAIA em
mensagens de interface para usuário final (marketer, aprovador, financeiro), sem substituir o `code` técnico
que a API já devolve — apenas acrescentando, para cada código, um título, uma mensagem e uma ação sugerida em
português.

### Fontes verificadas (lidas diretamente do Drive nesta sessão)

| Arquivo | fileId | Bytes | Conteúdo relevante |
|---|---|---|---|
| `campaia_core/errors.py` | `1QTFSVSLJw-sI2ok-Ic3vjpOOP9CqTlYB` | 1469 | `CampaiaError` + 8 subclasses de domínio |
| `api/errors.py` | `1N0MT1LTfc6oaw4rNlCxAHg96kz2EiqiU` | 3500 | `STATUS_BY_CODE` (18 códigos → HTTP), `ApiError`, `from_domain_error()` |
| `campaia_core/connectors.py` | `1LHyc0hcXenTHsj7RNDNXfqMhK1Eoa4Xp` | 4824 | `ConnectorErrorCode` (10 códigos), `NON_RETRYABLE`, `ConnectorError` |
| `campaia_core/permissions.py` | `1pFHGIQgGJO8plqzI-A8RYq9w8_henFta` | (lido inline) | `DenialCode` (3 códigos), `authorize()`, `can_approve()` |

Confirmei a pasta correta de `campaia_core/` (parentId `1qUAbtVmX6fHafW2MlHfHXrEcMo2y-5yx`) e `api/`
(parentId `1uYWRfiT5xiRegazwIoRMBG_mPkodfk0n`) cruzando o fileId de `main.py` contra o já conhecido e
verificado no fechamento da persistência real, evitando trabalhar sobre uma cópia desatualizada ou pasta
errada.

### Estrutura do catálogo

- **Seção 1** — tabela com os 18 códigos ativos de `STATUS_BY_CODE`, cada um com HTTP, título, mensagem e
  ação sugerida em português, mais 3 notas de aplicação (`assisted_flow_url`, não over-explicar causas
  variáveis, neutralidade deliberada do `KILL_SWITCH_ACTIVE` quanto ao escopo interno).
- **Seção 2** — narrativa de cobertura verificada: os 18 códigos batem exatamente com os 8 códigos de domínio
  (`campaia_core/errors.py`) e os 3 `DenialCode` (`campaia_core/permissions.py`).
- **Seção 3** — achado transparente: 3 dos 10 códigos de `ConnectorErrorCode` (`AUTH_EXPIRED`,
  `VALIDATION_REJECTED`, `PARTIAL_FAILURE`) não têm entrada em `STATUS_BY_CODE`, com evidência de que
  `VALIDATION_REJECTED` já é levantado por código real em `campaia_core/saga.py:191`. Mensagens propostas
  para os 3 códigos já ficam prontas, caso o Diretor autorize a correção de `api/errors.py`.
- **Seção 4** — limitações (dependência de D-03 para tom por segmento; nenhum teste com usuário real
  reivindicado).
- **Seção 5** — resumo.

## Verificação independente das alegações do documento

Antes de considerar o documento pronto, rodei um script Python comparando as alegações do catálogo contra os
arquivos-fonte reais (não contra a memória do que eu havia escrito):

```python
doc_codes_set = set(re.findall(r"\| `([A-Z_]+)` \|", section1))
real_codes = set(re.findall(r'["\']?([A-Z_]+)["\']?:\s*\d+', status_block))
# Resultado: MATCH exato, 18/18, sem faltantes e sem códigos extras

cec_codes = set(re.findall(r'([A-Z_]+) = "[A-Z_]+"', cec_block))  # membros de ConnectorErrorCode
# Resultado: gap = {'AUTH_EXPIRED', 'VALIDATION_REJECTED', 'PARTIAL_FAILURE'} — confirma exatamente o
# achado da Seção 3, sem diferença
```

Também confirmei via `grep` direto no conteúdo baixado de `campaia_core/saga.py` que `VALIDATION_REJECTED` é
efetivamente levantado na linha 191, não apenas um código-morto teoricamente alcançável.

## Upload ao Drive (com disciplina de verificação byte a byte — incluindo um erro real detectado e corrigido nesta própria tarefa)

| Arquivo | Ação | fileId | Bytes (Drive) | Bytes (local) | Match |
|---|---|---|---|---|---|
| `docs/09_CATALOGO_ERROS_USUARIO.md` (1ª tentativa) | Nova | `1w1OIsQbTVytY3Kc2CWWwtHO0wLowEQuM` | 12606 | 12603 | ❌ |
| `docs/09_CATALOGO_ERROS_USUARIO.md` (final) | Nova (após trash da 1ª) | `1spGTinX6n-SOULBFFala-vPYRpC7VEGc` | 12603 | 12603 | ✅ |

Nota de transparência: na primeira tentativa de upload, usei `textContent` retransmitindo o texto do
documento manualmente, e um erro de digitação meu (três caracteres residuais, "ple", antes do título)
acabou incluído apenas no conteúdo enviado à ferramenta — não no arquivo local, que permaneceu correto
(confirmado com `od -c` no início do arquivo local: começa exatamente em `# CAMPAIA`, sem qualquer prefixo
espúrio). O Drive relatou `fileSize: 12606`, 3 bytes a mais que o local (`wc -c` = 12603) — segui a mesma
disciplina de nunca presumir qual lado está certo: em vez de re-hospedar por cima ou assumir que o Drive
"arredondou" algo, movi o arquivo incorreto para a lixeira, gerei o base64 exato do arquivo local em disco
(`base64 -w0`) e reenviei via `base64Content` — eliminando qualquer risco de erro de transcrição manual. O
segundo upload bateu exatamente: 12603 = 12603. O arquivo incorreto (`1w1OIsQbTVytY3Kc2CWWwtHO0wLowEQuM`)
está na lixeira do Drive e não deve ser referenciado.

## Resumo

O catálogo de 18 mensagens de erro em linguagem de usuário do CAMPAIA está formalizado e publicado em
`docs/09_CATALOGO_ERROS_USUARIO.md`, com cobertura verificada programaticamente contra os arquivos-fonte reais
(`api/errors.py`, `campaia_core/errors.py`, `campaia_core/permissions.py`) e um achado transparente e
code-reachable de 3 códigos do Connector Hub (`AUTH_EXPIRED`, `VALIDATION_REJECTED`, `PARTIAL_FAILURE`) sem
mapeamento HTTP em `STATUS_BY_CODE`, com mensagens já propostas para os 3 caso a correção seja autorizada.
Um erro real de upload (discrepância de 3 bytes, causada por um erro de digitação meu no parâmetro de envio,
não no arquivo local) foi detectado por verificação byte a byte — não presumido nem ignorado — investigado
até a causa raiz, e corrigido antes de declarar o bloco fechado.
