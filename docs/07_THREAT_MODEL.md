# CAMPAIA — THREAT MODEL

**Versão:** 0.1 (PROPOSTA) · **Data:** 25/08/2026 · **Método:** STRIDE + categoria financeira própria

## 1. Ativos protegidos, em ordem de gravidade

| # | Ativo | Por que importa |
|---|---|---|
| 1 | Verba publicitária do cliente | Perda irreversível e imediata; destrói confiança |
| 2 | Credenciais OAuth de contas de anúncios | Comprometimento permite gasto, exclusão e acesso a dados de terceiros |
| 3 | Dados pessoais de clientes finais (listas, conversas de WhatsApp) | LGPD; dano ao titular; risco jurídico |
| 4 | Isolamento entre tenants | Uma falha contamina toda a base de clientes |
| 5 | Chaves de provedores de IA | Custo e abuso |
| 6 | Trilha de auditoria | Sem ela, nada é comprovável |
| 7 | Reputação de conta e número (qualidade WhatsApp, políticas de anúncio) | Recuperação lenta ou impossível |

## 2. Superfícies de ataque

App mobile · API do BFF · API pública para consumidores externos · OAuth callback · webhooks de provedores ·
saídas de LLM · painel administrativo · pipeline de CI/CD · dependências de terceiros.

## 3. Ameaças e controles

| ID | Ameaça | Superfície | Controle | Teste que comprova |
|---|---|---|---|---|
| T-01 | Token de sessão roubado no dispositivo | App | Sessão curta, refresh rotativo, step-up auth para conectar conta, elevar autonomia ou aumentar verba | Teste de autorização e de step-up |
| T-02 | Webhook forjado ou repetido | Webhooks | Verificação de assinatura, janela de tempo, dedupe por id externo | Teste de assinatura inválida e de replay |
| T-03 | Escalada horizontal entre tenants | API/BFF | RLS + autorização na aplicação; `tenant_id` derivado do token, nunca do corpo da requisição | Teste de isolamento com dois tenants |
| T-04 | Prompt injection via briefing ou conteúdo externo | LLM | Saída da IA é **proposta** validada por schema; nenhuma saída de LLM vira comando; sem ferramentas com efeito externo no gateway | Teste com payload malicioso tentando induzir publicação |
| T-05 | Vazamento de credencial em prompt ou log | LLM/observabilidade | Sanitizador determinístico; logs redigidos; segredo só no cofre | Teste que falha o build se token alcançar prompt, log ou resposta |
| T-06 | Gasto não autorizado por defeito ou loop de otimização | Domínio | Reserva de verba, limite diário/mensal/por ação, bloqueio de variação percentual, kill switch multinível | Teste financeiro: tentativa de exceder limite deve falhar |
| T-07 | Republicação duplicada por retry | Conectores | `idempotency_key` por comando; verificação de recurso existente antes de criar | Teste de idempotência com retry forçado |
| T-08 | Divergência silenciosa entre estado interno e plataforma | Conectores | Reconciliação periódica; estado derivado do provedor; alerta de divergência | Teste com estado alterado fora do sistema |
| T-09 | Uso indevido de lista de clientes / Customer Match | Domínio + LGPD | Base legal registrada; aprovação humana obrigatória; trilha de origem da audiência | Teste que bloqueia uso sem base legal |
| T-10 | Envio de WhatsApp sem consentimento | WhatsApp | Consentimento e opt-out obrigatórios em `whatsapp_consents`; envio bloqueado sem registro | Teste de envio sem consentimento deve falhar |
| T-11 | IA tentando ampliar a própria autonomia | Domínio | Autonomia é dado governado; nenhum caminho de escrita a partir do gateway de IA; mudança de nível exige aprovação humana | Teste arquitetural de dependência: gateway não importa conector nem governança |
| T-12 | Exaustão de cota de provedor por um tenant | Conectores | Cota por `external_account`; fila isolada; degradação com aviso | Teste de carga por tenant |
| T-13 | Comprometimento da cadeia de dependências | CI/CD | SAST, análise de dependências, lockfile, revisão de PR, segredo fora do repositório | Pipeline que falha em vulnerabilidade crítica |
| T-14 | Repúdio de aprovação | Governança | Aprovação registra ator, timestamp, versão do plano e evidência; trilha imutável | Teste de auditoria: reconstruir quem aprovou o quê |
| T-15 | Exfiltração via consumidor externo da API pública | API pública | `api_clients` com escopo mínimo, cota e trilha própria; nenhum acesso a dado de outro tenant | Teste de escopo e isolamento |

## 4. Controles não negociáveis (bloqueiam o Gate de Segurança)

1. Segredo em cofre, nunca no app, repositório, log ou prompt.
2. `tenant_id` derivado do token de autenticação, jamais aceito do cliente.
3. Toda mutação externa exige `policy_decision_id` válido e não expirado.
4. Kill switch funcional em cinco níveis: campanha, conta, tenant, plataforma, global.
5. Auditoria append-only para ação financeira e publicação.
6. MFA para administradores e perfis financeiros.
7. Nenhum caminho de código permite a um componente de IA executar efeito externo.

## 5. O que este threat model ainda não cobre

- ameaças específicas da nuvem escolhida (depende de D-08);
- modelo de ameaças de residência de dados e transferência internacional (depende de D-09);
- abuso por usuário legítimo do próprio tenant (fraude interna do cliente) — a tratar antes da Fase 9;
- ameaças ao processo de aprovação externa das plataformas (suspensão de conta, revisão de política).

Status: **PARCIAL**. Fecha no Gate de Segurança (G2), depois das decisões D-08 e D-09.
