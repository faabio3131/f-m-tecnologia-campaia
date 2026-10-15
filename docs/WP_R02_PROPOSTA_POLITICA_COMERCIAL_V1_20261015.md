# CampaIA — Proposta de política comercial V1

**Data:** 15/10/2026 · **Status:** HUMAN_DECISION — proposta, não aprovada.
**Base técnica:** main@1586ec120ea8d5ee0a06a9ec704f3719f4cd4254.
**Decisão solicitada:** aprovar o conjunto para implementação interna governada.
**Não autoriza:** publicação de preços, venda, produção, credencial real, pagamento, deploy ou migration real.

## 1. Decisão executiva proposta

Lançar três planos mensais, sem fidelidade anual, com franquia de créditos de uso e excedente
pós-pago autorizado. Crédito é uma unidade comercial por entrega, não token, dólar ou custo
bruto do modelo. A FM fornece e paga a IA; o cliente não fornece chave de IA.
Anúncios e serviços de terceiros não estão incluídos na mensalidade do CampaIA.

Os números abaixo são hipóteses comerciais propostas, não preços de mercado comprovados
nem margens certificadas. A aprovação permite construir/configurar/testar; a publicação
fica condicionada à medição de custos, homologação funcional e gates jurídicos/produção.

| Condição | Essencial | Profissional | Negócios |
|---|---:|---:|---:|
| Mensalidade proposta | R$ 149,00 | R$ 299,00 | R$ 599,00 |
| Créditos incluídos por ciclo mensal | 100 | 300 | 700 |
| Usuários ativos, incluindo OWNER | 2 | 5 | 15 |
| Campanhas ativas simultâneas | 3 | 10 | 30 |
| Crédito excedente, quando autorizado | R$ 1,00 | R$ 1,00 | R$ 1,00 |

Cada assinatura pertence a um tenant/organização. Unidades desse tenant compartilham a
franquia e os limites, preservando RBAC e isolamento. Outra empresa/tenant tem assinatura
própria. Um usuário que participa de duas empresas conta em cada assinatura.
Campanha multicanal conta como uma campanha interna; arquivar/pausar não apaga histórico.
O sistema deve verificar o limite ao publicar/retomar, sem interromper uma campanha ativa
por uma leitura atrasada de contador.

Os canais previstos para todos os planos são Google Ads, Meta/Facebook/Instagram e a
integração WhatsApp prevista no produto, somente quando estiverem homologados e liberados.
Não anunciar integração simulada, autorização externa pendente ou geração criativa incompleta
como recurso já entregue. Sem promessa de resultados, vendas ou retorno garantido.

Sem plano anual, desconto permanente, setup obrigatório, atendimento humano ilimitado,
vídeo ou plano Enterprise nesta primeira política. Futuras ofertas exigem outra versão.

## 2. Como os créditos serão consumidos

| Entrega solicitada pelo cliente | Débito proposto |
|---|---:|
| Estratégia completa de uma campanha | 5 créditos |
| Conjunto de textos com até 5 variações | 3 créditos |
| Proposta de público/segmentação | 2 créditos |
| Regeneração de uma variação de texto | 1 crédito |
| Análise de desempenho com recomendações | 5 créditos |
| Uma imagem padrão, até 1024 × 1024 | 15 créditos |

O pacote textual completo de uma campanha soma 10 créditos: estratégia + textos + público.
Se oferecido como pacote, esse é o débito total: não somar outra cobrança sobre as mesmas
etapas internas. A revisão de segurança/políticas obrigatória é gratuita para o cliente.

Pesos são configuração versionada, com limites de entrada/saída e de execução por operação.
Antes de executar, a UI informa o débito, eventual excedente e saldo disponível. Novas
regenerações expressamente solicitadas são novas operações; retries automáticos não são.
Rotinas de análise agendadas só consomem créditos após adesão explícita, com frequência e
estimativa de consumo visíveis. Nenhuma adesão automática.

Não consomem créditos: login, cadastro, edição manual, consulta de dados/métricas/histórico,
conexão de contas, aprovações, publicação, pausa, retomada, exportação prevista no produto,
kill switch e controles de segurança. Operações automáticas obrigatórias de segurança,
reconciliação, coleta de métricas, retries e fallback de IA são custo interno da FM.

O cliente só é debitado por entrega válida e disponibilizada. Falha técnica, resposta
inválida, bloqueio de política ou operação cancelada antes da entrega não geram consumo
comercial; o custo real do fornecedor continua no ledger interno da FM. Entrega concluída
antes de perda da resposta é debitada uma única vez e deve poder ser recuperada.

Reservar créditos antes de iniciar; liquidar no sucesso; liberar no insucesso conhecido.
Resultado externo incerto fica pendente de reconciliação, sem segundo débito. Livro
imutável com reversões explícitas: tenant, operação lógica, ação/peso/versionamento,
ciclo, reserva, conclusão e vínculo à entrega. Não cobrar a partir de contador do browser.

Imagem e demais ações ainda incompletas só entram na oferta quando cumprirem os gates
funcionais e de custo. O preço da tabela não representa homologação dessas funções.

## 3. Excedente com consentimento e sem surpresa

- Excedente desativado por padrão: limite adicional R$ 0,00.
- OWNER/FINANCE pode ativá-lo com step-up e aceite explícito. Sugestão inicial apresentada:
  teto de R$ 50,00 por ciclo; o cliente pode selecionar outro teto.
- Informar e registrar preço unitário, teto, ciclo e versão da política. A autorização vale
  até revogação; o limite monetário reinicia por ciclo e não autoriza aumento automático.
- Alertar em 80% e 100% da franquia e em 80% e 100% do teto adicional.
- Ao faltar autorização/saldo para toda a operação, não iniciar nova geração onerosa.
  Não gerar saldo negativo, cortar uma entrega no meio ou continuar gastando por suposição.
- Campanhas já publicadas, dados, métricas, aprovações humanas e pausa de emergência
  continuam acessíveis. Fim de créditos não pausa anúncios automaticamente.
- Créditos incluídos não acumulam entre ciclos. Excedente é consumo pós-pago, não carteira
  pré-paga; não cobrar por créditos extras não utilizados.

Exemplo: Essencial consumiu 120 créditos no ciclo, com autorização para exceder.
Excedente = max(120 − 100, 0) = 20 créditos; valor adicional = R$ 20,00.
Ao consumir 150 créditos, chega ao teto adicional de R$ 50,00. Uma operação que levaria o
consumo acima desse teto não começa sem nova autorização.

## 4. Trial

7 dias corridos, 30 créditos, 1 usuário e 1 campanha ativa simultânea; sem excedente,
sem cartão obrigatório, sem renovação paga automática. Os 30 créditos permitem, por exemplo,
um pacote textual de 10, uma imagem de 15 e uma análise de 5, quando esses recursos estiverem
homologados. Conta Google verificada e dados de contratação continuam no fluxo do produto.

Um trial por organização legítima. Desativar/reativar assinatura, trocar OWNER ou criar nova
sessão não reinicia o benefício. Antifraude pode correlacionar identidade/documento com
minimização de dados; IP compartilhado sozinho não prova abuso. Exceção exige revisão humana
auditada, sem concessão manual silenciosa no banco.

O trial inicia na confirmação, expira após 7 × 24 horas e não emite cobrança por conta própria.
Ao expirar, bloquear novas gerações pagas, preservando leitura/exportação e controles de
emergência. Conversão paga exige aceite e pagamento confirmado; abre nova franquia integral.
Saldo do trial não é somado à franquia paga e nenhuma cobrança retroativa é criada pelo teste.

## 5. Ciclo, cobrança e checkout

Mensal por aniversário da primeira ativação paga; fuso comercial America/Sao_Paulo e instantes
armazenados em UTC. A data original fica como âncora. Em mês sem esse dia, usar o último dia
válido e recuperar a âncora nos meses seguintes. Exemplo: dia 31 → último dia de fevereiro →
dia 31 de março. Períodos são semiabertos [início, fim), sem contagem dupla na fronteira.

- Primeiro pagamento: mensalidade antecipada do primeiro ciclo; ativação só após confirmação.
- Renovação: próxima mensalidade + excedente efetivamente consumido no ciclo anterior,
  em linhas separadas e rastreáveis. Não tratar o excedente anterior como uso da nova franquia.
- Sem juros, multa ou tarifa de gateway repassada adicionalmente nesta versão.
- Avisar 3 dias antes do aniversário, mostrando mensalidade e estimativa identificada de
  excedente, sem tratar estimativa como débito final. No aniversário, fechar o uso anterior
  e emitir uma única fatura com duas linhas/períodos: mensalidade seguinte e excedente anterior.
  Vencimento no próprio aniversário, com a carência definida na seção 7.
- Cartão ou outro débito autorizado só pode ser processado após fixar o total dessa obrigação.
  Não alterar uma cobrança já paga, estimar consumo futuro como realizado ou emitir duas
  mensalidades para resolver falha de integração. Correções posteriores são ajustes separados
  auditáveis, sem reemissão duplicada da mesma obrigação.
- Valores residuais abaixo do mínimo efetivamente configurado/validado do gateway acumulam
  como saldo identificável para cobrança futura; no encerramento definitivo, a FM absorve o
  residual abaixo desse mínimo. O exemplo técnico vigente usa R$ 5,00; validar com o gateway
  antes de publicar, sem pressupor que todo método/conta possui o mesmo mínimo.

Usar o motor interno CampaIA como autoridade única de ciclo e emissão por competência.
Não ativar simultaneamente um segundo agendador de assinatura nativa do Asaas para gerar a
mesma obrigação. A documentação do Asaas oferece recorrência própria, mas adotá-la no lugar
do agendador interno exigiria decisão arquitetural explícita e conciliação correspondente.

Checkout hospedado Asaas: Pix, boleto e cartão somente conforme disponibilidade/habilitação
da conta homologada. Recorrência de fatura não significa débito automático autorizado.
Cartão/Pix Automático exigem o consentimento específico aplicável; fora disso o cliente paga
cada fatura. Não coletar dados de cartão no CampaIA nesta versão.

O checkout mostra organização, titular, plano/versionamento, período, mensalidade, excedente
fechado, total, meio/ambiente e termos aceitos. Replays, duas abas e dois workers devem reutilizar
a mesma obrigação/fatura. IDs devem distinguir produto CampaIA, tenant, ciclo, finalidade e
instância de lifecycle, permitindo conciliação futura pelo Command sem misturar SaaS/clientes.
Webhook autenticado e reconciliado é autoridade de liberação; clique, redirect ou comprovante
inserido pelo cliente não são confirmação de pagamento.

## 6. Alteração de plano, cancelamento e reativação

**Upgrade e downgrade:** vigência no próximo aniversário, sem cobrança proporcional e sem
cobrar imediatamente um segundo mês completo. Plano atual continua até essa data. O pagamento
da nova obrigação não antecipa sozinho a vigência; saldo/limites novos entram no ciclo correto.
Excedente anterior usa o preço/versionamento do período em que foi consumido.

Downgrade só pode ser confirmado com usuários/campanhas dentro do novo teto. Após agendamento,
novas criações devem respeitar esse teto futuro para não inviabilizar a mudança; a UI deve
explicar esse efeito e permitir desistir do agendamento antes do fechamento. Não desativar
usuários/campanhas nem cobrar silenciosamente o plano maior para resolver incompatibilidade.

**Cancelar renovação:** padrão de cancelamento é terminar no fim do período já pago. Mantém
acesso nesse intervalo; não gera mensalidades posteriores. Excedente já autorizado/consumido
é devido e aparece no fechamento final. Disponibilizar encerramento imediato como opção
separada e expressamente confirmada, com informação do efeito no acesso e direitos de reembolso.

**Reativar:** antes do fim do período pago, retirar o cancelamento agendado sem cobrar de novo.
Depois de encerrado, nova mensalidade integral, nova instância de lifecycle e ativação após
pagamento confirmado; não conceder novo trial nem reutilizar fatura de reativação anterior.
Débito anterior permanece obrigação separada, sem somar à franquia como se fosse uso novo.
Não ativar nova renovação enquanto houver pendência vencida não resolvida.

Mudança de preço ou pesos não reprecifica contrato, consumo ou dívida retroativamente.
Propor aviso com 30 dias de antecedência para mudança de renovação e aceite registrado;
na falta de aceite, preservar condições antigas ou encerrar renovação sem novo débito,
conforme opção comunicada. Nunca promover o cliente silenciosamente para preço maior.

## 7. Atraso, carência e comunicação

Vencimento no aniversário; carência de 3 dias corridos. Lembretes no vencimento, D+2, D+3
e D+7, apenas enquanto a pendência existir e com dedupe. Sem duplicar lembretes do CampaIA e
Asaas para o mesmo gatilho; escolher o emissor operacional na integração.

Durante a carência, manter o acesso e apenas a franquia remanescente já paga; não conceder
nova franquia mensal sem pagamento confirmado. Após D+3, suspender novas gerações e novas
publicações/expansões pagas. Preservar acesso a faturas, dados, métricas, suporte, exportação,
pausa e kill switch. Atraso não autoriza apagar dados ou aumentar orçamento de anúncios.

Campanhas existentes podem continuar ativas nos provedores e gerando gasto de mídia: comunicar
isso claramente, mantendo o cliente capaz de pausá-las. Nenhuma pausa externa automática é
introduzida por esta política de cobrança. Pagamento confirmado recupera a obrigação/ciclo
corretos e não cria franquia duplicada, novo trial ou nova data de vencimento por acidente.

## 8. Garantia, estorno e dados

Proposta de garantia comercial: na primeira contratação paga, pedido feito até 7 dias após
o primeiro pagamento permite reembolso integral dos valores CampaIA pagos nesse intervalo,
inclusive excedente pago; processamento auditado e encerramento do acesso pago correspondente.
Não prometer restituição pelo CampaIA de gasto cobrado diretamente por Google/Meta/terceiros.

Essa garantia é adicional: não reduz direitos legais, não limita reclamações por cobrança
indevida e não estabelece exclusão genérica para renovação ou pessoa jurídica. O CDC prevê
o direito de arrependimento nas hipóteses do art. 49; aplicabilidade contratual deve ser
validada no gate jurídico, sem supor que todo contrato B2B tem o mesmo enquadramento.

Duplicidade ou cobrança indevida comprovada: correção/reembolso independentemente da janela
de garantia. Iniciar o tratamento em até 2 dias úteis; prazo de efetiva disponibilização é
informado conforme o provedor/meio, sem prometer liquidação instantânea. Não reutilizar ID
antigo para nova devolução nem registrar como devolvido antes da confirmação externa.

Após encerramento, disponibilizar exportação de dados operacionais por 30 dias; dados
financeiros/auditoria e exercício de direitos seguem retenção/base legal e política LGPD
aprovadas em F16. A presente proposta não determina eliminação automática de evidência fiscal.

## 9. Viabilidade e limites da aprovação

Metas propostas para validar antes de vender: custo direto total até 30% da receita CampaIA
e IA até 20%, avaliados por plano em cenário de consumo integral da franquia, retries,
fallback, análises automáticas incluídas e geração de imagens. Tributos, gateway, infraestrutura
alocada e suporte devem entrar na avaliação de contribuição, sem confundir receita com lucro.

| Plano | Orçamento máximo de IA/ciclo (20%) | Custo direto total/ciclo (30%) |
|---|---:|---:|
| Essencial | R$ 29,80 | R$ 44,70 |
| Profissional | R$ 59,80 | R$ 89,70 |
| Negócios | R$ 119,80 | R$ 179,70 |

São tetos-alvo para avaliação, não custos medidos nem promessa de margem. Medir modelos,
preços efetivos, câmbio, imagens, infraestrutura e taxas da conta real. Se a validação falhar,
parar a publicação comercial e voltar ao Diretor com números; não cortar créditos já
contratados nem aumentar preços aprovados silenciosamente. Custos internos ficam separados
do ledger comercial. A medição interna existente em memória não certifica esse gate.

## 10. CURRENT x implementação necessária

| Tema | CURRENT preservado | Delta após aprovação |
|---|---|---|
| Catálogo/configuração | Arquivo externo, valores fictícios de teste, fingerprint | Catálogo comercial versionado; condições aprovadas, sem segredo no Git |
| Entrada/trial | UI/API e duração configurável, trial opt-in | Franquia do trial e antifraude persistente |
| Uso | CostLedger interno em memória | Ledger durável de reservas/entregas/créditos, ciclo, versão, concorrência e reversões |
| Cobrança | Motor por competência, adapter Asaas, idempotência, webhook | Scheduler único, ciclo por aniversário, base antecipada/excedente fechado, quote/checkout completo |
| Plano/cancelar | Motor de pending plan e cancelamento imediato | Agendamento para próximo ciclo, cancelar renovação e vigência futura sem segunda mensalidade indevida |
| Reativar | Pending payment e pagamento confirmado | Identidade única por instância de lifecycle e tratamento de dívida/cancelamento agendado |
| Atraso | PAST_DUE/grace/dunning/recovery | Parametrização aprovada, escopos seguros de bloqueio e notificações reais |
| Histórico/fatura | UI paginada, metadados e URL validada | Linhas/obrigações de ciclos e excedentes, estorno e correlação futura Command |

A aprovação não permite reescrever blocos certificados sem lacuna demonstrada. Reutilizar
funções e persistência; estender somente os mecanismos necessários às regras novas.
Dados comerciais ficam configuráveis; nenhum tenant FM recebe privilégio especial.
Cada etapa exige contrato, auditabilidade, isolamento, replay, restart, concorrência,
Web/API, CI e evidências. Sandbox/simulador não são pagamento de produção.

## 11. Registro de aprovação solicitado

Sugestão de resposta do Diretor:

> Aprovo a Proposta de Política Comercial CampaIA V1 de 15/10/2026 como conjunto para
> implementação interna governada, incluindo planos, preços propostos, franquias, pesos,
> trial, excedente com consentimento, ciclo, alteração/cancelamento, atraso e garantia.
> Mantenho os gates de validação de custos, jurídico, credenciais, homologação e produção.

Até receber essa decisão: HUMAN_DECISION. Não transformar este documento em catálogo ativo.
Se aprovado, registrar data/autor/versão exata e iniciar o ledger durável e o ciclo/checkout,
sem repetir as telas, motor, histórico ou integrações já verificadas.

## Fontes e evidências

- ADR-0020: modelo híbrido + Asaas já aprovados; tabela real ainda não definida.
- AGENTS.md e Cronograma Mestre F0–F20/G0–G20: G5 e condições de autoridade.
- PRs #45/#46/#47 e CI pós-merge: plano/trial/histórico/fatura já integrados.
- backend/campaia_core/subscription.py: modos atuais de troca/cancelamento/reativação.
- backend/campaia_core/ai_gateway.py: CostLedger atual em memória.
- Consulta oficial em 15/10/2026: https://docs.asaas.com/docs/assinaturas — recorrência própria
  do gateway existe e criação de assinatura não confirma recebimento.
- Consulta oficial em 15/10/2026: https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm — art. 49.
- Referência de contexto, não equivalente funcional nem validação destes preços:
  https://reportei.com/planos-e-precos/ — oferta de relatórios com condições distintas.
