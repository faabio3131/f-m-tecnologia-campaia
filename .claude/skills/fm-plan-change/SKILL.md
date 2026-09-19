---
name: fm-plan-change
description: Planeja uma correção, funcionalidade ou evolução de software da Nova FM a partir do CURRENT comprovado, com Current→Target, critérios de aceite, impacto, riscos, testes, rollback e gates. Usar antes de implementação estrutural, mudanças transversais ou tarefas ambíguas. Não editar código durante o planejamento.
---

# FM Change Plan

Produzir um plano executável sem iniciar implementação.

## Requisitos

1. Ler `CLAUDE.md` e invocar `/fm-current-discovery` quando o CURRENT não estiver comprovado.
2. Definir objetivo, escopo autorizado, fora de escopo e critérios de aceite observáveis.
3. Identificar autoridades existentes, contratos, consumidores, dados e riscos afetados.
4. Separar claramente CURRENT, TARGET, hipóteses, decisões pendentes e evidências necessárias.
5. Selecionar a menor mudança coerente. Reutilizar implementação canônica antes de propor nova estrutura.
6. Para decisão arquitetural relevante, exigir System Design/ADR proporcional antes do código.
7. Definir estratégia de testes, segurança, migration, compatibilidade, observabilidade e rollback conforme o risco.
8. Dividir em blocos pequenos, cada um com entrada, mudança, validação e condição de parada.

## Proibições

- Não converter proposta em decisão.
- Não escolher stack, provider ou arquitetura sem autoridade/evidência.
- Não prometer compatibilidade ou viabilidade sem verificação.
- Não inserir trabalho conveniente que não seja necessário ao objetivo.

Encerrar com gate de planejamento e listar decisões que exigem autoridade humana.

