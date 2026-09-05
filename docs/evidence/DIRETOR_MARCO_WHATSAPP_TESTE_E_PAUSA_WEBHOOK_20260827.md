"# FONTE PRIMÁRIA — MARCO DE EXECUÇÃO: TESTE WHATSAPP CLOUD API CONCLUÍDO; PAUSA DELIBERADA NA CONFIGURAÇÃO DE WEBHOOKS

**Capturado em:** 27 de agosto de 2026
**Capturado por:** Claude, acompanhando em tempo real via prints de tela enviados pelo Diretor durante a execução
**Diretor:** Fábio Aluizio da Silva

---

## CONTEXTO

Sequência desta sessão: Business Manager "F&M Tecnologia" criada (ver `DIRETOR_MARCO_META_BUSINESS_MANAGER_CRIADA_20260827.md`) → App "CampaIA" criado no Meta for Developers, com casos de uso "API de Marketing" e "Conectar-se com clientes pelo WhatsApp" → seguindo recomendação técnica de Claude, priorizado o fluxo guiado do WhatsApp Business Messaging (Etapa 1: Experimente).

## SEQUÊNCIA DOS FATOS

1. Número de teste do WhatsApp gerado automaticamente pela Meta: **+1 (555) 205-3393**, com Phone Number ID e WhatsApp Business Account ID (Test WhatsApp Business Account) já disponíveis.
2. Token de acesso de teste gerado (temporário, não registrado em nenhum documento — mascarado na própria interface, consistente com a prática já seguida para o token do Google Ads).
3. Diretor autorizou o App "CampaIA" via OAuth (tela "Continuar como Fabio Silva?"), escolhendo deliberadamente **"Aceitar apenas as Contas do WhatsApp atuais"** (não "atuais e futuras") — por recomendação de Claude, seguindo o princípio de menor privilégio já praticado no projeto (coerente com ADR-0006).
4. Diretor cadastrou seu próprio número de celular como destinatário de teste (um dos até 5 permitidos), verificou por código enviado via WhatsApp, e enviou a mensagem de teste usando o template pré-aprovado "Confirmação de pedido".
5. **Mensagem de teste recebida com sucesso** no celular do Diretor — confirmando que a integração básica do WhatsApp Cloud API está funcional em ambiente de teste.
6. Diretor avançou para a **Etapa 2: Configuração de produção**, especificamente a seção de **Configurar webhooks** — que exige uma "URL de callback" (endereço público de um servidor do backend do CAMPAIA capaz de receber notificações de mensagens/status).

## DECISÃO: PAUSA DELIBERADA

Claude identificou que essa etapa não pode ser preenchida de forma real ainda: não existe backend do CAMPAIA hospedado publicamente — a infraestrutura real (Fase 2, Google Cloud, aprovada em D-08/ADR-0009) ainda não foi provisionada, pois a própria conta/projeto GCP real ainda não foi aberta (dependência externa listada em `04_DECISOES_DO_DIRETOR.md`, ainda não iniciada).

Esta pausa já havia sido prevista e registrada preventivamente no `CHECKLIST_CADASTROS_PLATAFORMAS_20260827.md` (Seção 3): *"Configurar webhooks... depende de o backend já ter um endpoint pronto para receber, o que só faz sentido próximo da Fase 7 real."*

**Resposta literal do Diretor, confirmando o registro deste ponto de parada:** "registre"

## STATUS RESULTANTE

- Business Manager, Página, App Meta e conta de teste do WhatsApp: **todos funcionais e confirmados** (mensagem de teste real recebida).
- Configuração de webhooks (Etapa 2 avançada): **deliberadamente pausada**, não por erro ou bloqueio externo, mas por dependência de infraestrutura real ainda não provisionada.
- Etapa 3 (Verificação da empresa/Business Verification): não iniciada — depende de documentação comercial (CNPJ da F&M Tecnologia, em processo, D-09/ADR-0011).

## PRÓXIMOS PASSOS CONDICIONAIS (quando retomado)

- Retomar a configuração de webhooks apenas quando o backend do CAMPAIA estiver hospedado com um endereço público real (pós-abertura da conta GCP e deploy inicial da Fase 2).
- Business Verification (Etapa 3) pode ser tentada antes disso, mas depende do CNPJ da F&M Tecnologia estar emitido.
- Nenhuma ação adicional necessária no WhatsApp de teste por ora — a funcionalidade básica já está validada.
"