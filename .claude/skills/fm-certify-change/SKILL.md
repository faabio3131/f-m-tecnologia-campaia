---
name: fm-certify-change
description: Certifica tecnicamente uma mudança, bloco, PR ou release da Nova FM com gates e evidências no mesmo HEAD. Usar quando o usuário perguntar se terminou, se está verde, se pode avançar, se está pronto, ou pedir auditoria final, homologação técnica ou readiness. Não fazer merge ou deploy durante a certificação salvo autorização explícita separada.
---

# FM Change Certification

## Baseline

1. Ler `CLAUDE.md` e confirmar repositório, branch, PR, HEAD completo, worktree e escopo certificado.
2. Confirmar critérios de aceite e matriz de gates aplicável.
3. Verificar que resultados anteriores pertencem ao mesmo HEAD; caso contrário, reexecutar ou marcar como não válidos para certificação.

## Certificação

1. Auditar diff, arquivos alterados, contratos, migrations, dependências e impacto de segurança.
2. Executar os comandos oficiais aplicáveis: lint, formatação, typecheck, testes focados/completos, integração, contrato, frontend, build, E2E, migration, segurança e smoke.
3. Registrar contagens e estados reais: sucesso, falha, pendente, cancelado, ignorado e não executado.
4. Não somar como verdes checks inexistentes nem tratar skip como cobertura equivalente.
5. Verificar CI, PR e sincronismo local/remoto quando fizerem parte do gate.
6. Confirmar ausência de debug residual, secret, alteração não autorizada e documentação enganosa.

## Veredito

Emitir somente um:

- `CERTIFICADO`: todos os gates obrigatórios aplicáveis estão comprovadamente verdes no mesmo HEAD;
- `CERTIFICADO COM PENDÊNCIAS NÃO BLOQUEANTES`: somente quando a norma permitir e cada pendência estiver explícita;
- `NÃO CERTIFICADO`: existe falha, ausência de evidência ou gate obrigatório pendente;
- `BLOQUEADO`: STOP condition ou dependência externa impede conclusão segura.

Informar separadamente o estado: `IMPLEMENTADO`, `INTEGRADO`, `TESTADO`, `HOMOLOGADO`, `PRONTO PARA PRODUÇÃO` ou `COMERCIALMENTE DISPONÍVEL`. Não promover um estado por inferência.

