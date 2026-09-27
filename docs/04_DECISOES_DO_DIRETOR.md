# CAMPAIA — DECISÕES RESERVADAS AO DIRETOR

**Data original:** 25/08/2026 · **Última atualização:** 27/08/2026 · **Autoridade:** Fábio Aluizio da Silva

Apresenta apenas o que a engenharia **não pode decidir sozinha**. Decisões técnicas rotineiras são tomadas
dentro da autonomia concedida (Ordem Mestra, item 17) e ficam registradas nas ADRs.

**Fonte das decisões D-03, D-05, D-06, D-09 (27/08/2026):** `docs/evidence/DIRETOR_DECISOES_D03_D05_D06_D09_20260827.md`, SHA-256 `0579d36008c49f453117d1365736dc58792c08d0173f2c405f6f17ba1a85269e`
**Fonte da decisão D-08 (27/08/2026):** `docs/evidence/DIRETOR_DECISAO_D08_INFRAESTRUTURA_20260827.md`, SHA-256 `468eb35f3d98f9ff7af51be658f3c28e462aa8b93c986ecfa0b55aaac6cab784`
**Fonte da pesquisa de valores exatos (27/08/2026):** `docs/evidence/PESQUISA_VALORES_EXATOS_GOOGLE_CLOUD_20260827.md`, SHA-256 `09c8513d55c572952a7793ded868a7308564c2242eb245e7f17f31bdd45da00c`

---

## Já resolvido — não requer decisão

| Item | Resolução | Fonte |
|---|---|---|
| Nome do produto | **CAMPAIA** | Diretor, 25/08/2026 (ADR-0001 APROVADA) |
| **D-02 — Relação com o Kordena** | **Independente, com integração futura opcional via API pública** | Diretor, 25/08/2026 (ADR-0002 APROVADA) |
| **D-03 — Segmento inicial** | **Qualquer pequeno negócio local (horizontal, sem vertical/nicho definido)** | Diretor, 27/08/2026 |
| **D-04 — Ordem de canais** | **Google Ads → Meta → operação conjunta → WhatsApp** | Diretor, 25/08/2026 (ADR-0007 APROVADA) |
| **D-05 — Objetivo primário do MVP** | **Os 4 objetivos de conversão (geração de leads, vendas no site, mensagens no WhatsApp, visitas físicas à loja) completos e configuráveis por cliente/tenant, já na primeira versão testada** — decisão do Diretor que substitui explicitamente a recomendação técnica original de "escolher um só" | Diretor, 27/08/2026 |
| **D-06 — Modelo comercial de IA** | **Híbrido: franquia de uso de IA inclusa no plano (custo nosso, com teto rígido por tenant) + créditos extras comprados pelo cliente ao ultrapassar a franquia** | Diretor, 27/08/2026 |
| **D-07 — Ambiente** | **Construir tudo que roda em Python puro sem PC; PC com VS Code fica para o fim** | Diretor, 25/08/2026 |
| **D-08 — Nuvem, região e orçamento de infraestrutura** | **Google Cloud Platform, região São Paulo (southamerica-east1)** — Cloud SQL (PostgreSQL), Memorystore (Redis), Pub/Sub, Cloud Workflows ou Temporal auto-hospedado (a definir com ADR-0004), Cloud Storage, Secret Manager. Valores oficiais confirmados para Cloud SQL (US$ 0,0413/hora por vCPU, US$ 0,007/GB-hora de memória, região São Paulo), e confirmado preço único mundial sem sobretaxa regional para Pub/Sub (US$ 40/TiB), Cloud Workflows, Secret Manager e Cloud Storage (≈US$ 0,02/GB/mês). ⚠️ **Único item ainda pendente:** preço de Memorystore (Redis) específico da região São Paulo — não obtido por depender de seletor JavaScript inacessível nesta sessão; Diretor instruiu manter como pendência isolada e avançar ("marque como pendente e vamos avançar"). | Diretor, 27/08/2026 |
| **D-09 — Entidade legal, LGPD e dados pessoais** | **Cada cliente contratante é o Controlador dos dados que insere; F&M Tecnologia é a Operadora, responsável pela segurança técnica dos dados no app.** ⚠️ Pré-requisito pendente: F&M Tecnologia ainda não tem CNPJ aberto (em processo) — bloqueia Fase 7/WhatsApp e uso real de listas de clientes até a constituição formal. Retenção, Termos de Uso e responsável nomeado ainda não redigidos. | Diretor, 27/08/2026 |
| Configurabilidade do produto | Cliente configura contas, marca, verba, canais, autonomia e IA — dentro de limites; travas de segurança não são desativáveis | Diretor, 25/08/2026 (ADR-0013) |
| Autonomia inicial | **Nível 1 — Aprovado** | Ordem Mestra §6 — fixado |
| IA sem credenciais e sem execução externa | Invariante obrigatório | Ordem Mestra §5 |
| Forma inicial do sistema | Monólito modular + workers + workflow durável | Ordem Mestra §7 (ADR-0003) |
| Event Sourcing | Não adotado no MVP | Ordem Mestra §8 (ADR-0004) |

---

## Decisões ainda abertas

Nenhuma decisão D-numerada permanece formalmente aberta em 27/08/2026. Ver seção seguinte para itens
derivados que ainda precisam de definição antes de cada decisão ser considerada totalmente implementável.

---

## Itens derivados das decisões de 27/08/2026 que ainda precisam de definição

Estes não são novas decisões D-numeradas, mas desdobramentos diretos das decisões acima que ainda faltam
fechar antes de considerar D-05, D-06, D-08 e D-09 totalmente implementáveis:

- **D-05:** tamanho de escopo de engenharia para suportar os 4 objetivos de conversão simultaneamente no MVP (pixel/Conversions API para leads e vendas; consentimento/templates para WhatsApp; mensuração para visita à loja) — a ser detalhado em `02_PLANO_MESTRE.md`.
- **D-06:** tamanho da franquia de IA por plano/tier comercial; mecanismo de medição de consumo em tempo real; fluxo de compra de créditos extras (sem processar cartão diretamente, conforme regra de segurança já estabelecida); regra de bloqueio ao esgotar franquia + créditos.
- **D-08:** preço de Memorystore (Redis) específico da região São Paulo (único item de orçamento ainda não confirmado — ver P-11); escolha final entre Cloud Workflows e Temporal auto-hospedado para o motor de saga; confirmação prática de que a região São Paulo do Google Cloud cumpre a expectativa de residência de dados assumida em D-09 (a pesquisa indicou alta confiança de disponibilidade de serviço, não constitui parecer jurídico).
- **D-09:** conclusão da abertura do CNPJ da F&M Tecnologia; redação de política de retenção; redação de Termos de Uso e Política de Privacidade; nomeação de responsável por privacidade.

---

## Dependências externas a iniciar

Prazos fora do controle da engenharia. Costumam ser o caminho crítico do projeto — recomenda-se iniciar em
paralelo à construção, sem esperar o app ficar pronto:

- projeto Google Cloud + OAuth client + **developer token** do Google Ads (o token novo começa em nível de
  conta de teste; níveis superiores passam por revisão);
- Meta App + Business portfolio + verificação de negócio + **App Review** quando exigido;
- Marketing API Access Tier da Meta — exige histórico real de chamadas com taxa de erro baixa, o que só se
  constrói usando o produto;
- WhatsApp Business Account, número comercial e templates;
- contas de desenvolvedor Apple e Google Play (necessárias apenas na Fase 12);
- **abertura formal do CNPJ da F&M Tecnologia** (decorrente de D-09, 27/08/2026) — pré-requisito para assumir formalmente o papel de Operadora de dados perante a LGPD/ANPD;
- **abertura de conta/projeto no Google Cloud Platform** (decorrente de D-08, 27/08/2026) — pré-requisito para qualquer trabalho de Fase 2 real de infraestrutura.

Nenhum desses itens foi solicitado, obtido ou simulado.

---

## Pendências de verificação (P)

| ID | Pendência |
|---|---|
| P-04 | Marca CAMPAIA: INPI, domínio e disponibilidade nas lojas |
| P-05 | Versão de Python do runtime de produção |
| P-08 | Meta: restrição a campanhas Advantage+ via Marketing API |
| P-09 | WhatsApp: mudanças de preço com vigência em 01/08/2026 e 01/10/2026 |
| P-10 | Documentação da Meta que exige acesso autenticado |
| P-11 | Preço de Memorystore (Redis) especificamente na região São Paulo — único item de orçamento do Google Cloud ainda não confirmado (decorrente de D-08; demais 5 serviços já confirmados em 27/08/2026, ver evidência de pesquisa de valores) |
