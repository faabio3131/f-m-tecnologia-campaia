# WP-R04-02 — Revisão seletiva de texto
CURRENT: main@2992cb61099ab32398297b270836fd62acea1cca (PR #69 e pós-merge verdes).
Status: PARTIAL / em validação.

## Escopo
Reutiliza agente copy, tabela 009 e execução durável. Escolhe uma variação do último
lote vigente, recebe instruções e gera somente um texto. Os outros textos são preservados.
A nova entrega append-only referencia o lote anterior/índice/instruções. Não edita a fonte.
Cotação usa a ação revision (1 crédito conforme política aprovada, quando configurada).
Não inventa preço ausente no catálogo real.

Troca de estratégia, lote mais recente, canal divergente, índice inexistente, autorização
revogada ou versão concorrente impedem entrega. Nova versão invalida revisão/aprovação.
Saída idêntica ou inválida não é entregue nem debitada; custo de provider permanece interno.
Replay incerto preserva reserva e não redispara. Revisão não autoriza publicação.

## Evidência exigida
API/Web/PostgreSQL/E2E com um texto alterado e demais idênticos, cobrança única,
rollback após escrever lote, restart/replay, concorrência, falha/timeout e isolamento.
Primeira CI confirmou API/PostgreSQL; corrigido comentário ausente nos tipos gerados.
Revisão final preserva contexto já entregue sem reinterpretá-lo como nova entrada do usuário.
CI final com Web/E2E no HEAD e pós-merge pendentes; registrar resultados na PR #70.

## Limites
Sem novo modelo, ativação de catálogo/credencial, migração real, GCS real ou gasto externo.
Não conclui imagens, preview por formato/canal, qualidade de conteúdo, moderação por IA,
performance ou G7. Permanecem os gates do cronograma mestre.
