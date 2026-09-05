"# FONTE PRIMÁRIA — MARCO DE EXECUÇÃO: CONTA DE GERENCIADOR GOOGLE ADS + TOKEN DE DESENVOLVEDOR CRIADOS

**Capturado em:** 27 de agosto de 2026
**Capturado por:** Claude, acompanhando em tempo real via prints de tela enviados pelo Diretor durante a execução
**Diretor:** Fábio Aluizio da Silva

---

## NATUREZA DESTE DOCUMENTO

Diferente dos demais documentos em `docs/evidence/`, este não registra uma decisão (D-xx), mas sim a **execução concreta** de um item já decidido e priorizado (ver `CHECKLIST_CADASTROS_PLATAFORMAS_20260827.md`, Seção 1 — Google Ads). Registrado por ter valor de rastreabilidade: é o primeiro ativo de credencial de plataforma da F&M Tecnologia efetivamente criado.

## SEQUÊNCIA DOS FATOS (guiada passo a passo via chat, sem acesso direto de Claude à conta)

1. Diretor identificou que seu e-mail pessoal já possuía 2 contas Google Ads (ambas "Cancelado", nenhuma do tipo gerenciador) — risco para o requisito oficial do Google de e-mail "nunca antes vinculado a uma conta Google Ads" para obtenção do token de desenvolvedor.
2. Diretor criou um e-mail novo e dedicado: `fmtecnologia.dev@gmail.com`.
3. Usando esse e-mail, em janela anônima, o Diretor tentou por duas vezes o fluxo padrão de "Nova conta do Google Ads", que o levou incorretamente ao assistente de criação de **campanha/conta de anunciante comum** (não é o tipo de conta necessário) — identificado e corrigido antes de qualquer campanha ser configurada.
4. Diretor então acessou `business.google.com/br/ad-tools/manage-accounts/` e usou o botão oficial "Criar uma conta de administrador", chegando ao formulário correto de conta de **gerenciador (MCC)**.
5. Conta de gerenciador criada com sucesso: **nome "F&M Tecnologia", ID de conta 975-498-3401**, uso principal "Gerenciar as contas de outras pessoas", país Brasil, fuso horário São Paulo (GMT-03:00), moeda Real brasileiro (BRL).
6. Diretor acessou o **Centro de API** (`ads.google.com/aw/apicenter`) dentro dessa conta de gerenciador.
7. Preencheu o formulário de acesso à API:
   - E-mail de contato da API: `fmtecnologia.dev@gmail.com`
   - Nome da empresa: F&M Tecnologia
   - URL da empresa: link da landing page institucional publicada (artifact Claude) — usada para satisfazer o requisito de "site funcionando"
   - Tipo de empresa: **Desenvolvedor independente do Google Ads** (opção escolhida após análise conjunta das 4 opções disponíveis — Anunciante, Agência/SEM, Afiliado, Desenvolvedor independente — por ser a que descreve com mais precisão uma empresa de software que constrói uma aplicação própria consumindo a API, em vez de uma agência operando campanhas manualmente)
   - Uso pretendido (texto submetido): "Plataforma de software (SaaS) chamada CAMPAIA, desenvolvida pela F&M Tecnologia, que permite a pequenas e médias empresas gerenciar suas próprias campanhas de marketing digital de forma assistida por inteligência artificial. Cada cliente conecta sua própria conta do Google Ads via OAuth e mantém total propriedade e controle sobre seus dados e campanhas. O sistema auxilia na criação, otimização e publicação de campanhas, sempre com aprovação humana explícita antes de qualquer ação de publicação ser executada."
   - Sede da empresa: Brasil
8. Diretor revisou e aceitou o **Google Ads API Terms and Conditions** (contrato formal entre F&M Tecnologia e Google LLC), em nome da empresa, na qualidade de Diretor com autoridade para tal.
9. Token de desenvolvedor gerado com sucesso.
10. Diretor confirmou, via print da tela "Central de API → Acesso à API", que o token está mascarado corretamente na interface do Google (não exposto em texto plano) e que o nível de acesso exibido é **"Conta de teste"**.

## RESPOSTA LITERAL DO DIRETOR

> "feito criou a api"

## STATUS RESULTANTE (CONFIRMADO)

- Conta de gerenciador Google Ads da F&M Tecnologia: **criada e ativa** (ID 975-498-3401).
- Token de desenvolvedor da Google Ads API: **criado e confirmado** — nível de acesso exibido na interface do Google Ads (Central de API → "Acesso à API"): **"Conta de teste"** (Test Account Access), conforme esperado para um token recém-criado. Funciona apenas contra contas de teste do Google Ads; elevação para "Acesso básico" ("Basic Access") ou "Acesso padrão" ("Standard Access") para uso com contas reais de clientes exige solicitação adicional na própria seção "Nível de acesso" e revisão do Google, sem prazo garantido — passo futuro ainda não iniciado, sem urgência no momento. O valor literal do token não foi e não deve ser registrado em nenhum documento (mascarado na própria interface do Google); quando a integração técnica real começar, deve ser armazenado exclusivamente em cofre de segredos (Secret Manager, GCP), nunca em texto plano.
- Nenhuma conta de anúncio comum foi vinculada a esta conta de gerenciador durante o processo — evitado corretamente, conforme orientado.
- Item correspondente no `CHECKLIST_CADASTROS_PLATAFORMAS_20260827.md` (Seção 1): sub-itens de criação de conta de gerenciador, acesso ao API Center, preenchimento do formulário e aceite dos termos — **concluídos e confirmados**. Pendente apenas a eventual solicitação futura de elevação de nível de acesso.

## O QUE ESTA EXECUÇÃO NÃO RESOLVE

- Nenhuma integração técnica real entre o backend do CAMPAIA e esta credencial foi iniciada — esta é uma etapa de registro/cadastro de plataforma, não de engenharia.
- Não substitui nem inicia o cadastro em Meta/WhatsApp (Seção 2 e 3 do checklist), que seguem como próximos itens.
- Não resolve o armazenamento seguro futuro do token (cofre de segredos) — item de engenharia a ser tratado apenas quando a integração técnica real for iniciada.
"