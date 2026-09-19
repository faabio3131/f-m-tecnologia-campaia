# ADR-0017 — Framework de frontend Web

**Status:** PROPOSTA · **Data:** 19/09/2026 · **Aprovador proposto:** Fábio Aluizio da Silva

## Contexto

Nenhum frontend Web existe hoje em nenhum dos dois repositórios do CampaIA (confirmado por auditoria). A Lei Web First (ADR-0016) exige que a linha evolutiva principal nasça Web. É preciso escolher a base tecnológica do frontend antes de qualquer scaffold.

## Restrições

- Não escolher por popularidade; comparar critérios reais.
- Deve consumir a API HTTP existente (`bff-openapi.yaml`, 21 rotas) sem exigir mudança de contrato.
- Deve suportar SSR ou CSR conforme necessidade real (área pública com SEO vs. dashboard autenticado).
- Deve ser compatível com Chrome 100+, Firefox 100+, Safari 15+ (NFR §8.3, preservado).
- Não instalar nem fazer scaffold nesta missão — só decidir e registrar.

## Opções analisadas

| Opção | Vantagem | Custo/Risco | Reversibilidade |
|---|---|---|---|
| **A — Next.js/React (recomendada)** | SSR nativo para a área pública (SEO); CSR para o dashboard autenticado na mesma base; ecossistema maduro; App Router permite rotas protegidas com middleware de sessão; boa curva de manutenção; sem lock-in de vendor específico (pode implantar em qualquer runtime Node) | Curva de aprendizado de SSR/RSC para quem não conhece o framework; decisões de cache do framework exigem disciplina | Alta — é React puro por baixo; migrar para outra base React-compatível é possível |
| B — React com SPA/Vite | Mais simples de raciocinar (sem SSR); build rápido | Sem SSR nativo — área pública perde SEO a menos que se adicione solução separada; autenticação/rotas protegidas exigem mais código manual | Alta |
| C — Outra alternativa (Vue, Svelte, Angular) | Podem ter vantagens pontuais de performance/DX | Equipe e ecossistema do projeto (Python/Starlette, TypeScript não confirmado em uso prévio) não têm precedente com nenhuma dessas — maior risco de curva de aprendizado sem benefício comprovado | Média |

## Comparação (critérios do prompt mestre)

| Critério | Next.js/React | SPA/Vite | Outra |
|---|---|---|---|
| SSR | Nativo | Não nativo | Depende |
| SEO da área pública | Bom | Fraco sem extra | Depende |
| Dashboard autenticado | Bom (CSR via client components) | Bom | Depende |
| Segurança (CSP, cookies HttpOnly) | Suportado nativamente | Suportado, mais manual | Depende |
| Testes | Ecossistema maduro (Testing Library, Playwright) | Idem | Depende |
| Observabilidade | Integrações prontas (Vercel/OpenTelemetry) | Manual | Depende |
| Custo operacional | Baixo (pode rodar como container Node comum, não exige vendor específico) | Baixo | Depende |
| Compatibilidade com backend Starlette | Total — só precisa da API REST | Total | Total |
| Maturidade | Alta | Alta | Variável |
| Lock-in | Baixo (Node padrão) | Baixo | Variável |

## Recomendação

**Next.js/React**, sem lock-in de vendor de deploy específico (implantação a decidir em ADR-0019, sobre a infraestrutura já aprovada — Google Cloud, D-08).

## Decisão

Registrada como **PROPOSTA** — não aprovada. Aguarda decisão humana explícita antes de qualquer scaffold.

## Consequências

Fica mais fácil: uma única base cobre área pública (SSR) e dashboard autenticado (CSR), sem duas stacks separadas. Fica mais difícil: exige disciplina de cache/revalidação do App Router para não misturar dado de tenant entre requisições — mitigado adiante em Work Packages com testes de isolamento cross-tenant na camada Web (ver `docs/web/04_...md` §4, Gate 4 de `docs/web/05_...md` §3).

## Riscos

| Risco | Mitigação |
|---|---|
| Cache de SSR vazar dado entre tenants | Nunca cachear resposta autenticada no nível de framework sem chave por sessão/tenant; testar explicitamente no Gate 4 |
| Complexidade de RSC confundir onde a autorização realmente ocorre | Reforçar, em toda implementação, que autorização é sempre servidor (BFF/domínio), nunca decisão de componente React |

## Reversibilidade

Alta — nenhum código foi escrito; a escolha é anterior a qualquer scaffold.

## Gatilho de revisão

Se, durante o scaffold (Gate 2), surgir incompatibilidade real e comprovada com a infraestrutura de implantação escolhida em ADR-0019, revisar.

## Pendências

Aprovação humana explícita antes do Gate 2 (Scaffold Web).
