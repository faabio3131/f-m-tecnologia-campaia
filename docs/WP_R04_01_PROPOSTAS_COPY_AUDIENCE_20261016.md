# WP-R04-01 — Propostas textuais de copy e público

CURRENT: main@89a1063e056b230c3223aad272338da4fa7a0921, PR #68 e pós-merge verdes.
TARGET deste delta: ligar agentes copy/audience existentes à campanha e à revisão humana.
Status: PARTIAL / em validação. Evidências finais na PR; não declara G7 concluído.

## Entrega
- Lotes de 1–5 textos (3 créditos por lote) e propostas de público (2 créditos).
- Tenant/unidade/autoridade verificados antes da chamada e novamente na entrega.
- Contexto congelado de estratégia/briefing/marca; arquivos removidos bloqueiam novas chamadas.
- Histórico privado append-only por tipo, provenance, versão e indicação de contexto vigente.
- Reserva antes do provider; provider fora da transação; material + versão + auditoria + SETTLE atômicos.
- Falha conhecida libera reserva; resultado externo incerto mantém reserva sem redispatch.
- Um único vencedor por versão de plano entre workers. Replay conserva corpo/chave/cobrança.
- Entrega invalida validação/aprovação; publicar exige versão atual e tipo PUBLISH.
- Política de revisão dupla não pode ser reduzida por campo enviado pelo cliente.
- Default simulado de estratégia não anuncia capacidade copy/audience inexistente.
- Fixture task-aware explicitamente test-only para E2E; não certifica Gemini real.

## Verificação
Testes API/PG incluem rollback após inserir material, replay após restart, isolamento,
revogação durante geração, conteúdo inválido/Unicode, concorrência e aprovação antiga.
Contrato e tipos sincronizados são obrigatórios. UI e E2E devem confirmar o fluxo e o débito.
CI completa no HEAD e pós-merge são condições de integração, ainda pendentes neste registro inicial.

## Limites
009 apenas em fonte/CI; sem migration real. Cloud SQL permanece desligado.
Nenhuma ativação/credencial/custo real, deploy, pagamento ou publicação externa.
Não há imagem, seleção de variante para exportar, limites/preview de formato Google/Meta,
targeting de plataforma, performance ligada nem eval de qualidade aprovado neste delta.
F7/G7 continua PARTIAL. Homologação GCS/Gemini real e demais gates mestres permanecem externos.
