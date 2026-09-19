# CampaIA — Registro formal: mobile em quarentena arquitetural

**Data:** 19/09/2026
**Contexto:** Reconciliação controlada `faabio3131/CampaIA` → `faabio3131/f-m-tecnologia-campaia` (repositório canônico), conforme ADR-0014.
**Autor:** Claude, por instrução explícita do Diretor.

---

## ESTADO FORMAL

**QUARENTENA ARQUITETURAL — NÃO CERTIFICADO COMO PRODUTO COMERCIAL E NÃO DECLARADO COMO LINHA PRINCIPAL**

Aplica-se a todo o diretório `mobile/` (app Flutter/Dart: fluxos de Onboarding e Nova Campanha).

## O QUE A QUARENTENA SIGNIFICA

- **Código preservado.** Nenhum arquivo de `mobile/` foi excluído, reescrito ou movido nesta reconciliação.
- **Nenhuma evolução nesta fase.** Nenhuma nova tela, estado ou integração deve ser adicionada a `mobile/` enquanto esta quarentena estiver vigente.
- **Nenhuma declaração de prontidão.** `mobile/` não deve ser referido como "pronto", "integrado", "testado" ou "homologado" em nenhum documento ou comunicação, sob qualquer circunstância.
- **Nenhuma dependência do futuro frontend Web.** O System Design da aplicação Web real (ainda não produzido) não deve presumir, herdar ou depender de nenhuma decisão tomada em `mobile/`.
- **Decisão final pendente de System Design e autoridade humana.** O destino de `mobile/` — promovido a app oficial complementar, reclassificado formalmente como protótipo descartável (Documento Mestre §47), ou mantido indefinidamente em quarentena — não foi decidido nesta reconciliação e não deve ser presumido.
- **Flutter não substitui a aplicação Web exigida pela Lei Web First** (Documento Mestre §5). A existência de `mobile/` não satisfaz, parcial ou totalmente, a obrigação de que todo novo software comercial da Nova FM Tecnologia nasça Web First.

## POR QUE A QUARENTENA (evidência técnica)

Conforme já documentado em `mobile/README.md` (linhas 76-96, texto original do bloco B8), o próprio autor original registrou que o SDK Flutter/Dart estava ausente da sandbox onde o código foi escrito, e que `flutter analyze`/`flutter test` **nunca foram executados de fato** — apenas uma verificação estática manual (balanceamento de chaves, resolução de imports, revisão pontual de duas APIs sensíveis à versão).

## VERIFICAÇÃO NESTA RECONCILIAÇÃO (19/09/2026)

Comando executado: `which flutter dart`
Resultado: **ambos ausentes** neste ambiente também.

Conforme instrução explícita desta reconciliação, o SDK **não foi instalado** para tentar validar esta etapa.

**Status: NÃO VERIFICADO.** `flutter analyze` e `flutter test` continuam nunca tendo sido executados de fato sobre este código, em nenhum ambiente documentado até esta data.

## PRÓXIMOS PASSOS (fora do escopo desta reconciliação)

1. Executar `flutter pub get && flutter analyze && flutter test` em um ambiente com o SDK real antes de qualquer decisão sobre o destino de `mobile/`.
2. Produzir o System Design da aplicação Web (Ponto Zero Web) antes de decidir se/como `mobile/` se relaciona com a linha evolutiva principal.
3. Levar a decisão de destino (promover / reclassificar / manter quarentena) ao Diretor, com autoridade de FM Solution Architect, conforme já registrado no plano de reconciliação da auditoria anterior.
