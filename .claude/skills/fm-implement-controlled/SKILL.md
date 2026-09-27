---
name: fm-implement-controlled
description: Implementa mudanças de software previamente compreendidas e autorizadas na Nova FM com alteração mínima, preservação arquitetural, testes e evidências. Usar quando o usuário pedir para construir, corrigir, refatorar ou integrar código. Não usar para merge, deploy ou produção sem autorização explícita separada.
---

# FM Controlled Implementation

## Pré-flight

1. Ler `CLAUDE.md` e confirmar escopo, repositório, branch, HEAD e estado do worktree.
2. Confirmar CURRENT suficiente, critérios de aceite e plano. Se faltar, parar e executar descoberta/planejamento.
3. Inspecionar instruções locais e comandos oficiais de validação.
4. Preservar alterações preexistentes e evitar arquivos fora do escopo.

## Implementação

1. Criar ou ajustar testes que demonstrem o comportamento quando isso for tecnicamente adequado.
2. Implementar a menor mudança coerente na autoridade correta.
3. Não duplicar regra crítica no frontend, controller, adapter ou provider.
4. Tratar caminhos negativos, erro, autorização, tenancy, concorrência e idempotência conforme o risco.
5. Não adicionar dependência, migration ou breaking change sem justificativa e plano.
6. Revisar o diff continuamente para detectar expansão de escopo, dead code, debug residual e exposição de dados.

## Validação

1. Executar primeiro os testes focados; corrigir causa raiz.
2. Executar lint, typecheck, testes, build e demais gates aplicáveis definidos pelo repositório.
3. Não enfraquecer gates para obter verde.
4. Associar resultados ao HEAD testado.
5. Se um gate obrigatório não puder ser executado, não certificar; registrar a pendência.

Não fazer merge, deploy, release ou alteração de produção como consequência implícita da implementação.

