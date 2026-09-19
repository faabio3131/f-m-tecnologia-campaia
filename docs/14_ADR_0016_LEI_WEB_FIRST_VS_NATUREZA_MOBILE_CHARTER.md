# ADR-0016 — Precedência da Lei Web First sobre a declaração de natureza mobile do Product Charter

**Status:** PROPOSTA · **Data:** 19/09/2026 · **Aprovador proposto:** Fábio Aluizio da Silva

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

## Decisão proposta

**Recomendação: Opção B**, ainda não aprovada.

Uma distinção importa aqui: a Lei Web First **já é obrigatória** por autoridade institucional vigente (`docs/nova-fm/00-DOCUMENTO-MESTRE-NOVA-FM-TECNOLOGIA.md` v2.0, hierarquicamente superior a documento de produto, conforme `CLAUDE.md`) — isso não depende desta ADR nem de nenhuma aprovação adicional. **O que esta ADR propõe, e que permanece pendente de aprovação humana, é especificamente o tratamento formal da divergência**: registrar que a frase "Natureza: Aplicativo mobile SaaS independente" do Product Charter e o tratamento de Web como "Fase 12" do NFR estão, a partir de agora, superados por essa norma já vigente — e deixar a correção literal desses dois documentos, se aprovada, para decisão humana explícita, em vez de reescrevê-los automaticamente nesta missão.

Se aprovada, esta ADR passa a valer como registro formal dessa precedência para toda decisão arquitetural futura do CampaIA; o restante do Charter e do NFR (público-alvo, canais, autonomia, guardrails) permanece válido e é reaproveitado neste Ponto Zero Web (ver `docs/web/02_PONTO_ZERO_WEB_E_REQUISITOS.md` §1.2) independentemente da aprovação desta ADR específica.

A atualização literal do texto do Charter/NFR **não é executada por esta ADR em nenhuma hipótese** — fica registrada como pendência para decisão humana explícita, conforme o prompt mestre desta missão proíbe alteração de documentos de produto fora de escopo.

## Razão

Reescrever documentos de produto é uma decisão de produto, não uma decisão arquitetural — pertence à autoridade do Diretor (Documento Mestre §55.2, FM Product & Market), não a esta missão de System Design.

## Consequências

Fica mais fácil: toda decisão arquitetural deste Ponto Zero Web tem base clara de autoridade, sem ambiguidade sobre qual norma prevalece. Fica mais difícil: o Charter/NFR continuam com uma frase tecnicamente desatualizada até que o Diretor a corrija formalmente.

## Riscos

| Risco | Mitigação |
|---|---|
| Alguém ler o Charter isoladamente e concluir que o CampaIA é mobile-first | Esta ADR e o Ponto Zero Web tornam a precedência explícita e rastreável |
| Atualização do Charter nunca acontecer | Registrado como pendência explícita em `docs/web/07_CERTIFICACAO_PONTO_ZERO_WEB.md` §Decisões pendentes |

## Reversibilidade

Alta — nenhuma alteração de código ou de documento de produto foi executada; a reversão desta ADR é apenas documental.

## Gatilho de revisão

Quando o Diretor decidir formalmente o texto atualizado do Charter/NFR, esta ADR deve ser marcada como superseded pela atualização formal.

## Pendências

Atualização literal de `CAMPAIA_PRODUCT_CHARTER.md` §1 e `NON_FUNCTIONAL_REQUIREMENTS.md` §8 — decisão humana, fora do escopo desta missão.
