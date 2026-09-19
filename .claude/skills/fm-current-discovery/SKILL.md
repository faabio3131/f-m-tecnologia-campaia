---
name: fm-current-discovery
description: Descobre e documenta o CURRENT técnico comprovado antes de mudanças. Usar em auditorias, onboarding, retomada de trabalho, reconciliação documental, investigação de repositório, branch, PR, CI, arquitetura, contratos, banco, testes ou quando houver dúvida sobre o estado real. Permanecer somente em leitura salvo autorização explícita posterior.
---

# FM Current Discovery

Executar descoberta proporcional ao impacto sem alterar estado externo.

## Procedimento

1. Ler o `CLAUDE.md` e localizar as normas, o System Design, os ADRs e os contratos relevantes.
2. Confirmar repositório, remoto, branch padrão, branch atual, HEAD completo, worktree e alterações preexistentes.
3. Identificar PRs, checks, workflows e evidências ligadas ao mesmo HEAD quando acessíveis.
4. Mapear somente o recorte necessário: autoridades, módulos, dados, contratos, consumidores, integrações, segurança e testes.
5. Confrontar documentação com código e execução. Registrar divergências sem escolher silenciosamente uma narrativa.
6. Não usar memória de conversa como prova do estado técnico atual.

## Saída

Organizar em:

- `FATOS CONFIRMADOS`, cada um com evidência;
- `HIPÓTESES`, com método proposto de verificação;
- `DECISÕES VIGENTES`, com fonte;
- `TARGET`, sem apresentá-lo como implementado;
- `PENDÊNCIAS E CONTRADIÇÕES`;
- `GATE`: `APROVADO`, `APROVADO COM PENDÊNCIAS NÃO BLOQUEANTES` ou `BLOQUEADO`.

Se a evidência necessária não estiver acessível, declarar `NÃO VERIFICADO`. Não preencher lacunas por inferência.

