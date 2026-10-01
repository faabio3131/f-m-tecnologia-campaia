# CampaIA — FRONTEIRA FORMAL F3 × F4 × F17 — 01/10/2026

**Objetivo:** impedir retrabalho e dupla contagem entre runtime, infraestrutura e resiliência operacional.

## Regra de separação

| Item | Dono primário | Evidência exigida |
|---|---|---|
| Adapter PostgreSQL e seleção por configuração | F3 | testes de código + PostgreSQL real no CI |
| Schema CURRENT, migrations e rollback lógico | F3 | migration up/down/up |
| Atomicidade, locks, idempotência e crash/replay | F3 | testes concorrentes/multi-process |
| Shared session/step-up/OAuth/dedupe | F3 | 2+ processos compartilhando DB |
| Tenant isolation no banco | F3 | query scoping + guard DB + negative path |
| Rate limit distribuído de aplicação | F3 | múltiplos processos sob mesmo limite |
| Projeto/ambientes GCP | F4 | recurso externo provisionado |
| Serviço de container | F4 | configuração reproduzível |
| Cloud SQL real | F4 | instância/connection/IAM reais |
| Secret Manager/KMS | F4 | recursos/policies reais |
| Rede privada/service IAM | F4 | configuração externa reproduzível |
| Migration gate no deploy | F4 | pipeline staging real |
| Backup automático/PITR gerenciado | F4 | configuração/evidência Cloud SQL |
| Restore ensaiado | F17 | teste de recuperação real |
| RPO/RTO medidos | F17 | exercício de DR |
| Valores-alvo RPO/RTO | HUMAN_DECISION | decisão de risco/custo do Diretor |

## Decisão de isolamento

RLS foi avaliado conforme o Cronograma Mestre. O CURRENT não usa uma policy RLS genérica porque existem stores com lookup pré-tenant, especialmente sessões. Em vez de criar bypasses especiais, F3 implementa:

- `tenant_id` nos predicados SQL para repositories tenant-scoped;
- ownership de tenant imutável no banco para rows tenant-owned;
- triggers PostgreSQL contra re-home;
- fail-closed no RecordTable quando um ID pertence a outro tenant;
- testes cross-tenant e raw-SQL negative path.

Essa decisão é específica do runtime CURRENT e não impede hardening adicional por RLS seletivo em F16.

## Backup/restore sem falsa homologação

O requisito de backup/restore/RPO/RTO continua visível porque aparece na F3 do Cronograma Mestre. Porém não existe Cloud SQL/staging real neste WP. Logo:

- código/runtime F3 não finge “backup automático”;
- F4 deve provisionar e configurar a capacidade gerenciada;
- F17 deve executar restore e medir os tempos/pontos reais;
- nenhum número de RPO/RTO é inventado antes de decisão humana e medição.

## Gate

O Gate G3 pode ser certificado independentemente da existência de Cloud SQL real porque seu critério explícito é comportamento de 2+ réplicas sem perda de sessão, OAuth state, idempotência, approval ou isolamento. Essa prova foi feita contra PostgreSQL 16 real no CI.

G4, G17, G18 e G19 permanecem abertos.
