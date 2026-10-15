# WP-R02-09 — Revisão e emissão de pagamento

CURRENT: main@667a646e6d7701173c73cbc26c8be54d3d481daa, PR #52 integrada.
PR #52 no HEAD 141aab4eb0dabb6ff66e88e9e1dcbc1405f559f8: Backend 38814946783,
Frontend 38814946950, F4 38814946819 SUCCESS.
Pós-merge: Backend 38815178852, Frontend 38815178999, F4 38815178910 SUCCESS.

## Delta do checkout

GET /billing/checkout usa a mesma autoridade de cálculo da emissão, sem consultar o gateway,
criar obrigação ou conceder franquia. Informa disponibilidade, plano/créditos/preço extra,
linhas e total, período pago conhecido, vencimento e ambiente. Primeiro período só recebe
datas definitivas quando o pagamento fixa sua âncora; não apresentar estimativa como contrato.
Titular é minimizado pelo final do documento, sem CPF/CNPJ completo ou customer_ref na resposta.

A Web permite revisar os valores, exige checkbox de aceite e autenticação recente e envia
fingerprint com CSRF/idempotência. Alteração de valor/período/ambiente requer nova revisão.
Aceite é auditado no mesmo freeze financeiro. Chamadores internos anteriores continuam
compatíveis sem os campos novos; essa compatibilidade não autoriza novos débitos automáticos.

O retry preserva chave/corpo. Reabrir a página recupera a obrigação já congelada e a fence
do WP-R02-08 impede segunda emissão. Registro da cobrança nunca é exibido como pagamento;
assinatura/franquia continuam dependentes do webhook autenticado/reconciliado. Histórico
existente é atualizado e o link Asaas só é mostrado no host e ambiente permitidos.

Vencimento V1 acompanha o aniversário no fuso America/Sao_Paulo; emissão inicial vence no
dia comercial da solicitação. O adaptador recebe essa data, sem aplicar o prazo legado de
três dias à obrigação V1. Valor, vencimento e ambiente observados devem coincidir com o
snapshot. Provedor/ambiente congelados impedem emissão/consulta no ambiente trocado após
uma resposta incerta. Fluxos legados mantêm sua configuração anterior.

Preços V1 precisam ser finitos e exatos em centavos, dentro dos limites existentes do ledger;
checkout não arredonda condições silenciosamente. Emissão V1 envia multa/juros zero conforme
política aprovada. Confirmar essa configuração e formas de pagamento na homologação real;
os testes com MockTransport não certificam configurações da conta nem liquidação bancária.

## Verificação

- API: leitura sem emissão/freeze, minimização do documento, isolamento, aceite obrigatório,
  fingerprint alterado, preço/ambiente mudados, registro sem ativação, duas linhas na renovação,
  emissão incerta, vencimento divergente, renovação cancelada e ambiente congelado.
- Adaptador: data comercial na fronteira UTC/São Paulo e payload sem multa/juros adicionais.
- PostgreSQL: revisão e aceite reais na rota antes da prova de freeze entre workers.
- Web: revisão + checkbox + step-up, CSRF, retry exato, ausência de emissão antecipada,
  cancelamento, ambiente de simulação honesto e rejeição de URL externa indevida.
- Novo E2E dedicado usa Next/Starlette reais, SQLite e IdP determinístico: duas abas revisam
  antes da emissão, solicitam simultaneamente e devem receber uma única cobrança SIMULATOR,
  mantendo acesso bloqueado. Harness separado preserva o E2E de sessão certificado.
  Catálogo fictício temporário, nenhum endpoint de bypass, nenhuma credencial/rede financeira.
  Esse cenário depende do CI Chromium; não relatar como passado antes do resultado.

Local: domínio 424 e API 375 testes passaram (19 PostgreSQL reservados ao CI); Web check
passou com lint/types/drift/boundaries, 105 testes e build. Resultados finais/HEAD exato na PR.

Primeiro CI da PR #53 no HEAD c87bbbb06d70740b83e121644529803533e18858:
Backend 38816907535 e F4 38816907506 SUCCESS; Frontend 38816907509 falhou no E2E novo.
Os 28 cenários existentes de sessão passaram. O artefato checkout-e2e-evidence mostrou
checkout duplicado após a atualização da página: checkout e consumo compartilhavam a mesma
key React entre irmãos. Correção: prefixos de identidade distintos. Novo teste de integração
da página confirma atualização conjunta de assinatura/histórico com um único checkout,
mensagem de registro preservada e ausência de aviso de chave duplicada. A suíte Web passa a
106 testes; cenário de duas abas mantido integralmente para repetir no novo HEAD.

Fontes primárias conferidas em 15/10/2026:
- https://docs.asaas.com/reference/criar-nova-cobranca — value, dueDate, externalReference,
  UNDEFINED e efeitos da configuração global de juros/multa; criar cobrança não confirma pagamento.
- https://docs.asaas.com/docs/webhook-para-cobrancas — estrutura de fine/interest no pagamento.

## Limites e próxima etapa

F5/G5 permanecem PARTIAL: scheduler único, aviso prévio e dunning deduplicados, fechamento
final de excedente sem mensalidade posterior, cancelamento/conciliação de fatura aberta,
ajustes/refunds/chargebacks/residual mínimo, custos e homologação externa continuam pendentes.
Vencimento já passado e métodos habilitados exigem prova externa antes de oferta pública;
não modificar obrigação congelada nem criar segundo invoice para contornar rejeição do gateway.
Termos jurídicos públicos, suporte e garantias mantêm seus próprios gates de aprovação.

Não há migration nova nem alteração de preços reais por default. Campos opcionais ficam no
envelope comercial. Rollback exige bloquear writers/dispatch V1 e preservar snapshots/fences;
writers antigos não podem descartar novos metadados financeiros. Nenhum deploy, credencial,
migration real, cobrança externa ou religamento Cloud SQL foi executado.
