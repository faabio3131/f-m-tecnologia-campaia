# ADR-0016 — Precedência da Lei Web First sobre a declaração de natureza mobile do Product Charter

**Status:** APROVADA · **Data da proposta:** 19/09/2026 · **Data da aprovação:** 19/09/2026 · **Aprovador:** Fábio Aluizio da Silva

## Contexto

`docs/product/CAMPAIA_PRODUCT_CHARTER.md` §1 (redigido em 26/08/2026, antes da governança Nova FM) declara literalmente: **"Natureza: Aplicativo mobile SaaS independente"**. `docs/product/NON_FUNCTIONAL_REQUIREMENTS.md` §8 trata "Mobile (Flutter)" como plataforma primária e relega "Web Dashboard" à Fase 12.

Em 13/09/2026 (v1.0) e 17/09/2026 (v2.0), `docs/nova-fm/00-DOCUMENTO-MESTRE-NOVA-FM-TECNOLOGIA.md` §5 instituiu a Lei Web First: "Todo novo software comercial da Nova FM Tecnologia deve nascer como produto Web desde sua concepção." `CLAUDE.md` estabelece que, em caso de divergência, a norma institucional prevalece sobre documentação histórica — mas exige que a divergência seja "registrada e reconciliada", não silenciosamente sobrescrita.

## Restrições

- Não alterar os documentos de produto silenciosamente durante esta missão (proibição explícita do prompt mestre).
- Não alterar os dois documentos normativos da Nova FM (Documento Mestre, Padrões de Construção).
- Preservar toda decisão de negócio válida do Charter (público-alvo, canais, autonomia, guardrails) que não seja Web-incompatível.

## Opções analisadas

| Opção | Vantagem | Custo/Risco | Reversibilidade |
|---|---|---|---|
| A — Ignorar a divergência, seguir com Web sem tocar no Charter | Nenhum esforço documental extra | Documentação de produto permanece factualmente incorreta; risco de confusão futura sobre "o que é o CampaIA" | Alta, mas deixa dívida documental |
| **B — Registrar a divergência e propor a precedência formal da Lei Web First sobre a frase específica de natureza (esta ADR), deixando a atualização literal do Charter para decisão humana** | Resolve a divergência de autoridade sem executar uma decisão de produto não solicitada | Exige que o Diretor formalize a atualização do Charter depois | Alta |
| C — Reescrever o Charter agora, unilateralmente | Documentação fica imediatamente consistente | Decisão de produto tomada sem autorização humana explícita — proibido pelo prompt mestre e pelo Documento Mestre §56 (coordenação não é usurpação) | Baixa (mudança de produto já publicada) |

## Decisão

**Opção B — APROVADA** pelo Diretor Fábio Aluizio da Silva, autorização atual e explícita registrada em 19/09/2026 ("PROMPT MESTRE — APROVAÇÃO ARQUITETURAL E MERGE CONTROLADO").

A Lei Web First **já era obrigatória** por autoridade institucional vigente desde sua adoção (`docs/nova-fm/00-DOCUMENTO-MESTRE-NOVA-FM-TECNOLOGIA.md` v2.0) — isso nunca dependeu desta ADR. O que esta ADR formaliza, agora com aprovação humana explícita, é o tratamento da divergência: a frase "Natureza: Aplicativo mobile SaaS independente" do Product Charter e o tratamento de Web como "Fase 12" do NFR estavam superados por essa norma já vigente, e essa divergência está **reconciliada nesta mesma aprovação** — não apenas registrada.

**Atualização literal executada** (autorizada explicitamente pelo Diretor, item 5 da autorização de 19/09/2026): `docs/product/CAMPAIA_PRODUCT_CHARTER.md` §1 e `docs/product/NON_FUNCTIONAL_REQUIREMENTS.md` §8 foram atualizados nesta mesma execução — natureza do produto passa a "Produto Web SaaS independente", mobile explicitamente marcado como quarentena arquitetural e cliente complementar futuro, "Fase 12"/"Web Dashboard" removidos do framing de compatibilidade. Público-alvo, canais, autonomia governada e guardrails financeiros do Charter permanecem integralmente preservados, sem redesenho de produto.

## Razão

Reescrever documentos de produto é uma decisão de produto, não uma decisão arquitetural — pertence à autoridade do Diretor (Documento Mestre §55.2, FM Product & Market), não a esta missão de System Design.

## Consequências

Fica mais fácil: toda decisão arquitetural deste Ponto Zero Web tem base clara de autoridade, sem ambiguidade sobre qual norma prevalece. Fica mais difícil: o Charter/NFR continuam com uma frase tecnicamente desatualizada até que o Diretor a corrija formalmente.

## Riscos

| Risco | Mitigação |
|---|---|
| Alguém ler o Charter isoladamente e concluir que o CampaIA é mobile-first | **Mitigado**: `CAMPAIA_PRODUCT_CHARTER.md` §1 atualizado nesta aprovação, declara Web como natureza e linha principal |
| Atualização do Charter nunca acontecer | **Resolvido**: atualização literal executada nesta mesma aprovação (19/09/2026) |

## Reversibilidade

Alta — nenhuma alteração de código ou de documento de produto foi executada; a reversão desta ADR é apenas documental.

## Gatilho de revisão

Nenhum pendente — a atualização formal do Charter/NFR já ocorreu nesta mesma aprovação. Revisão futura só se necessária por nova decisão de produto.

## Pendências

Nenhuma pendência desta ADR específica. Pendências reais do System Design Web mais amplo (provedor de identidade, serviço de container, orçamento e residência de dados de D-08) permanecem registradas em `docs/web/07_CERTIFICACAO_PONTO_ZERO_WEB.md`, sem relação com esta ADR.
