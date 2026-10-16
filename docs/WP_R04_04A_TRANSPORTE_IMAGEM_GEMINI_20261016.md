# WP-R04-04A — Transporte interno de imagem Gemini

CURRENT: main@957d99a7804f6a6d3e2b6379cbf58fbd280976fd, PR #71 e pós-merge verdes.
Status: PARTIAL / em validação. Não é ativação nem conclusão de G7.

## Fonte primária consultada em 16/10/2026
- https://ai.google.dev/gemini-api/docs/image-generation
- https://ai.google.dev/gemini-api/docs/interactions-overview
- https://ai.google.dev/gemini-api/docs/pricing

Interactions aceita POST autenticado, texto de entrada e formato image/png, 1:1, 1K.
A saída binária está nos blocos image de model_output; output_image é conveniência do SDK.
store=false evita persistência da interação e não permite reutilizar histórico.
A implementação não solicita ferramentas, busca, execução em background ou edição por referência.
O adaptador de texto existente permanece inalterado.

## Delta
- GeminiImageProvider opt-in; sem modelo/tarifa padrão. Variáveis GEMINI_IMAGE_* separadas.
- Nenhuma leitura de chave de texto quando desativado; nenhuma ligação a AppState/API/Web.
- Contexto com limite, sanitização e trava de credenciais antes do HTTP.
- Origem/path fixos, TLS padrão, sem proxy de ambiente/redirect/retry; resposta/corpo/tempo limitados.
- Uma imagem final inline, MIME PNG, base64 canônico e no máximo 5 MiB.
- Decodificação/normalização pelo mesmo worker Linux restrito dos assets; PNG final verificado.
- Metadados/thoughts/URLs não viram imagem entregue; sem download de URI fornecida na saída.
- Uma geração por instância de provider de cada vez. Fechamento e indisponibilidade não despacham.
- Bloqueio, erro, resposta parcial e uso desconhecido permanecem explicitamente distintos.

## Custo
input/output_usd_per_million e pricing_reference são configuração obrigatória para ativar.
Usa contagens inteiras observadas e taxa de saída conservadora para imagens/texto/thinking,
com arredondamento para cima. A evidência é UNVERIFIED_ESTIMATE, não fatura/margem real.
Uso ausente/inválido não é zero nem saída bem-sucedida. Timeout/erro HTTP são UNKNOWN.
Taxas vigentes, câmbio, taxas e margem precisam de homologação; não foram ativados valores.
Uma instância sem fallback/retry será exigida na ligação do fluxo durável; replay é tarefa
do claim F3, não uma capacidade de idempotência externa inventada para o Google.

## Verificação
MockTransport, sem rede/chave real: forma da requisição, configuração OFF, custos, schema,
PII/credenciais, PNG normalizado, bloqueios, uso ausente, timeout, headers, tamanho, URI,
múltiplas imagens e integração com AIGateway. CI completa no HEAD e pós-merge são exigidas.

## Próximos deltas
Persistência/metadata de criativos por campanha, quota e armazenamento privado, fence de
upload/reconciliação, API/Web, confirmação e entrega atômica de 15 créditos somente quando
funcional. Verificar worker/GCS/modelo em runtime real, qualidade e aplicação visual da marca.
Não ativa catálogo, credencial, modelo real, migration, deploy ou Cloud SQL. Não inclui logo/
foto como entrada do modelo nem afirma preview nativo Google/Meta/WhatsApp.
