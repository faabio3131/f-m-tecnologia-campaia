# WP-R02-07 — Lifecycle comercial por aniversário

CURRENT: main@03a59c875a7f7f2363a9afc4c84f6bedd983309c, PR #50 integrada.
Pós-merge PR #50: Backend 38810917891, Frontend 38810917895 e F4 38810917885 SUCCESS.
TARGET deste bloco: aplicar a política V1 aprovada ao lifecycle sem alterar contratos legados.
Autorização contínua de engenharia/merge registrada em AGENTS.md §11; produção não autorizada.

## Comportamento entregue

- Troca V1 somente no próximo aniversário e após pagamento da obrigação daquele período.
  Exige fingerprint do catálogo revisado, snapshot contratado na fatura e mensalidade integral.
  Pagamento antecipado não muda o plano antes da data nem move a âncora original.
- Downgrade valida usuários ativos/convites e campanhas ocupando vaga. O menor limite futuro
  restringe expansão; desistência antes do fechamento restaura os limites atuais.
- Cancelar renovação preserva acesso até o fim de todos os períodos pagos. Encerrar agora é
  ação distinta e explícita. Consumo registrado continua consultável sem autorização de extras.
- Remover cancelamento antes do fim preserva a mesma contratação, sem nova fatura. Após o
  encerramento, nova solicitação exige lifecycle novo e pagamento integral, sem repetir trial.
  Dívida vencida do mesmo tenant impede nova contratação. Pagamento antigo não ativa a nova.
- Refresh temporal usa a transação/lock F3 do tenant; requisição de leitura não sobrescreve
  mudança financeira concorrente. Webhooks preservam liquidação separada da liberação de acesso.
  OVERDUE atrasado não substitui SETTLED. Grants usam o período e os termos efetivamente pagos.
- Gateway observa o valor retornado, inclusive em recuperação por externalReference; divergência
  ou ausência desse valor bloqueia o registro/ativação V1 para reconciliação.
- Web exige revisão, autenticação recente, CSRF e chave estável em retry incerto. Datas e
  limites vêm do servidor. O aviso sobre continuidade de gastos de anúncios externos permanece.

## Verificação

Novos cenários de domínio/API cobrem vigência + pagamento, reativação antes/depois do fim,
identidade nova, invoice antiga, snapshot divergente, dívida e isolamento entre tenants,
downgrade ocupado, desistência e preservação do acesso pago. PostgreSQL amplia o cenário
de dois workers com cancelamento/removal do agendamento observado pelo outro worker.

Também corrigido o isolamento do teste Firebase de JWT inválido: credencial anônima explícita
e asserção de nenhuma requisição de rede. Não busca Application Default Credentials/metadata
nem modifica a autenticação de produção. Resolve o risco apontado pela revisão automática
da consulta anterior de teste; nenhuma credencial real é necessária.

Local: domínio 420 testes; API 357 (19 PostgreSQL dependem do CI); Web 101 testes esperados,
lint/types/drift/boundaries/build. Resultado final/HEAD exato e CI registrados na PR.
Isso não constitui revisão independente de segurança, homologação externa ou conclusão G5.

## Próximo delta e limites

WP-R02-08 deve congelar obrigação antes do efeito no gateway, oferecer reconciliação da janela
de falha, fechar excedente final sem nova mensalidade, coordenar emissão/dunning únicos e
cancelamento de faturas abertas. O fail-closed por valor desta etapa não substitui essa outbox.
Refunds/chargebacks, valor mínimo gateway, custo real, reconciliação de geração incerta,
homologação financeira real e decisões jurídicas continuam pendentes antes de ativar V1.

Sem nova migration: campos opcionais no envelope comercial persistente. Rollback para writer
antigo pode perder metadados; exige bloquear/drenar writers financeiros e despacho comercial,
preservar ledger e reconciliar obrigações. Não executar rollback vivo sem plano aprovado.
Sem credenciais/cobrança externa, deploy, migration real ou religamento Cloud SQL.
