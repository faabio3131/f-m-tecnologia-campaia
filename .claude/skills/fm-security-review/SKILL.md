---
name: fm-security-review
description: Revisa segurança de mudanças, PRs, fluxos e releases da Nova FM, especialmente autenticação, autorização, sessões, RBAC/ABAC, multi-tenancy, unidade, PII, secrets, APIs, webhooks, migrations, pagamentos e operações destrutivas. Usar quando houver superfície sensível ou antes de readiness de produção.
---

# FM Security Review

Executar revisão baseada em evidência e no risco real do escopo.

## Verificações

- Identidade, autenticação, expiração e invalidação de sessão.
- Autorização no servidor, least privilege e prevenção de escalada.
- Isolamento de tenant/unidade e tentativas de spoofing.
- Validação de entrada, saída segura e tratamento fail-closed.
- Secrets, tokens, hashes, PII e dados sensíveis em código, logs, frontend e artefatos.
- Idempotência, replay, assinatura e duplicação em webhooks/ações críticas.
- Concorrência, transações, integridade, migrations e operações destrutivas.
- Dependências, providers, configuração, auditoria e observabilidade.
- Caminhos negativos e testes adversariais proporcionais.

## Classificação

Para cada achado, registrar evidência, impacto, explorabilidade, escopo afetado e correção recomendada. Marcar falso positivo ou hipótese como tal.

Cross-tenant access, bypass de autenticação/autorização, escalada indevida, secret exposto, fraude crítica, corrupção de dados, destruição não autorizada ou vulnerabilidade crítica conhecida são `STOP DE PRODUÇÃO`.

Não declarar “seguro”. Declarar apenas o escopo revisado, evidências, riscos encontrados e limitações da análise.

