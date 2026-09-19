---
name: fm-debug-root-cause
description: Diagnostica falhas, regressões, erros de CI, testes quebrados e comportamento inesperado por causa raiz, produzindo correção mínima e teste de regressão quando autorizado. Usar quando algo falhar, estiver intermitente, divergente ou sem explicação comprovada.
---

# FM Root-Cause Debugging

## Diagnóstico

1. Ler `CLAUDE.md` e preservar o estado inicial.
2. Registrar sintoma, ambiente, HEAD, comando e saída real.
3. Reproduzir de forma mínima e controlada. Se não reproduzir, declarar a limitação.
4. Formular hipóteses testáveis e procurar evidência que possa refutá-las.
5. Distinguir falha primária de falhas em cascata; não contar a cascata como múltiplas causas.
6. Usar logs, testes, histórico e diff sem revelar secrets ou PII.

## Correção

1. Localizar a autoridade responsável pelo comportamento.
2. Corrigir a causa raiz com a menor mudança coerente.
3. Adicionar teste de regressão que falhe antes e passe depois quando aplicável.
4. Não mascarar com retry indiscriminado, exceção engolida, fallback inseguro, timeout ampliado sem evidência, `skip`, `xfail` ou assert removido.
5. Executar novamente o caso reproduzido e os gates de regressão aplicáveis.

Relatar causa confirmada, evidência, correção, cobertura de regressão e incertezas remanescentes. Se a causa não for comprovada, não apresentá-la como fato.

