# ADR-0018 — Autenticação e sessão Web

**Status:** PROPOSTA · **Data:** 19/09/2026 · **Aprovador proposto:** Fábio Aluizio da Silva

## Contexto

Hoje não existe autenticação real: `api/deps.py` usa um token fixo de teste, explicitamente não uma credencial real (confirmado no painel v18/v19). O domínio de autorização (`permissions.py`) já está completo — RBAC, ABAC, MFA, step-up — mas não tem nenhuma fonte real de identidade alimentando-o. `docs/product/NON_FUNCTIONAL_REQUIREMENTS.md` §4.1 já propunha OAuth 2.0 + JWT (24h) + refresh token (30 dias) + MFA obrigatória para admins como TARGET, nunca implementado.

## Restrições

- Tenant ativo nunca por header não confiável.
- Cookies de sessão `HttpOnly`, `Secure`, `SameSite`.
- CSRF token em mutações.
- Compatível com o `Principal` já definido em `permissions.py` (não redesenhar essa estrutura).
- MFA/step-up devem alimentar exatamente os campos já existentes (`mfa_enabled`, `step_up_at`) sem alterar o domínio.

## Opções analisadas

| Opção | Vantagem | Custo/Risco | Reversibilidade |
|---|---|---|---|
| **A — Provedor de identidade gerenciado (OAuth/OIDC) integrado ao BFF via sessão de cookie server-side (recomendada)** | Sem gestão própria de senha/hash; MFA e recuperação de conta ficam a cargo do provedor; sessão via cookie `HttpOnly` reduz superfície de XSS/roubo de token no cliente | Depende de escolha de provedor (a decidir — não antecipar vendor específico sem pesquisa de custo/portabilidade) | Média — trocar de provedor OIDC é trabalho real, mas não catastrófico (padrão aberto) |
| B — Autenticação própria (senha, hash, sessão) | Controle total | Superfície de risco de segurança alta para equipe pequena — mesma objeção já registrada em `docs/09_ADR_0013_CREDENCIAIS_E_CONFIGURABILIDADE.md` para credenciais de plataforma, aplicável aqui também | Baixa depois de usuários reais existirem |
| C — Token JWT armazenado em `localStorage`, sem cookie | Simplicidade de implementação inicial | Exposto a XSS por design — contraria a exigência de "cookies seguros" do próprio prompt mestre e a prática recomendada de segurança Web | Baixa |

## Comparação

| Critério | A (OIDC + cookie) | B (própria) | C (JWT em localStorage) |
|---|---|---|---|
| Risco de XSS roubar sessão | Baixo (`HttpOnly`) | Depende da implementação | Alto |
| Esforço de manutenção | Baixo | Alto | Baixo |
| MFA | Delegado ao provedor | Construído do zero | Depende |
| Compatibilidade com `Principal` existente | Total (mapear claims → `Principal`) | Total | Total |
| Alinhamento com NFR §4.1 (OAuth 2.0) | Direto | Indireto | Parcial |

## Recomendação

**Opção A.** A escolha do provedor específico (ex.: gerenciado pela nuvem já decidida em D-08, ou um provedor de identidade dedicado) fica para o Work Package de implementação, não para esta ADR — decidir provedor específico sem pesquisa de custo/portabilidade seria repetir o erro que ADR-0013 já preveniu para credenciais de plataforma.

## Decisão

Registrada como **PROPOSTA** — não aprovada.

## Consequências

Fica mais fácil: `permissions.py` recebe um `Principal` real sem precisar ser alterado. Fica mais difícil: o mapeamento de claims do provedor de identidade para `roles`/`business_unit_ids` precisa de um Work Package próprio de provisionamento (convite de usuário, atribuição de papel por tenant).

## Riscos

| Risco | Mitigação |
|---|---|
| Sessão Web definir tenant ativo a partir de dado do cliente | Proibido explicitamente — tenant ativo só a partir de claim de sessão validada no servidor, cruzada contra tenants do `user_id` |
| Elevação administrativa (step-up) sobreviver a troca de tenant | Troca de tenant/unidade deve invalidar `step_up_at` |

## Reversibilidade

Média — ver comparação acima.

## Gatilho de revisão

Se o provedor de identidade escolhido no Work Package de implementação não suportar multi-tenancy adequadamente, revisar.

## Pendências

Escolha do provedor específico (Work Package); aprovação humana explícita antes do Gate 3 (Autenticação).
