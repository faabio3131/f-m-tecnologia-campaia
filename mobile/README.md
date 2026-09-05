# CampaIA — App Mobile (Flutter)

Fase 8 do painel de execução (`backend/01_PAINEL_EXECUCAO_v18_VIGENTE.md`).
Stack: Flutter + Dart (decisão já registrada em `docs/05_ARQUITETURA_V2.md`
§6, `docs/product/NON_FUNCTIONAL_REQUIREMENTS.md` §8.1 e
`docs/10_PLANO_AQUI_VS_PC.md`, bloco C6).

## Estado desta fatia (05/09/2026)

### Fatia 1 — Onboarding (F1.1–F1.5)

Primeiro passo do caminho crítico recomendado no painel v18: a tela de
**Onboarding**, especificada em
`docs/product/13_ESPECIFICACAO_TELAS_APP.md` §3.

Construído nesta fatia:

- Estrutura de pastas *feature-first* (`lib/features/onboarding/`), separando
  `screens/` (as 4 telas), `widgets/` (componentes reutilizáveis) e `state/`
  (o modelo de estado do fluxo).
- `OnboardingState` — um `ChangeNotifier` puro cobrindo as 4 etapas do mapa
  de navegação (§2 da especificação) e a regra de negócio "Concluir
  Onboarding habilitado assim que pelo menos um canal estiver conectado"
  (§3.4).
- As 4 telas: Login (3.1), Cadastro da Empresa (3.2), Unidade de Negócio
  (3.3, com "Adicionar depois") e Conectar Contas (3.4, 3 cartões
  independentes por canal).
- Testes unitários de `OnboardingState` (navegação e a regra de habilitação
  do botão final) em `test/features/onboarding/onboarding_state_test.dart`.

### Fatia 2 — Fluxo de Nova Campanha (caminho crítico, §6/§9)

Segundo passo do caminho crítico: as 3 telas do fluxo de Nova Campanha
pedidas nesta etapa — uma consolidação das 5 etapas completas da
especificação (§6.1–6.5) em 3 telas, mais a integração com a regra de
autonomia (§9.1/9.1.1):

- `lib/features/new_campaign/state/new_campaign_state.dart` —
  `NewCampaignState` (`ChangeNotifier` puro), cobrindo as 3 etapas e os
  tipos de domínio necessários (`CampaignObjective`, `CampaignChannel`,
  `AutonomyMode`, `AutonomyLimits`, `ChannelCreative`, `CreativeVariant`).
- **Tela 1 — Objetivo e Canal** (`objective_and_channel_screen.dart`):
  objetivo primário/secundários (§6.1) e seleção dos 3 canais, com a regra
  "só aparecem os canais já conectados" (§3.4/§6.1) refletida via
  `connectedChannels` (ainda sem integração real com o estado de conexões
  do onboarding — ver Próximos passos).
- **Tela 2 — Orçamento e Regra de Autonomia**
  (`budget_and_autonomy_screen.dart`): orçamento total, e os dois modos de
  autonomia (§9.1) lado a lado — Manual (Nível 1) selecionado por padrão, e
  Automático (Nível 2) só ativável via `AutomaticModePasswordDialog`
  (§9.1.1, Passo 3). Aviso fixo e sempre visível de que campanha **nova**
  nunca pula a aprovação humana, em nenhum modo.
- **Tela 3 — Revisão e Prévia do Criativo**
  (`review_and_creative_preview_screen.dart`): resumo da campanha, prévia
  por canal com variações de criativo e selo de verificação de política
  (§6.3), e botão "Enviar para Aprovação" — nunca "Publicar", reforçando a
  regra da §6.5 ("nenhuma campanha é publicada sem sua aprovação").
- Testes unitários em `new_campaign_state_test.dart`, com foco extra nas
  duas regras mais sensíveis: o Modo Automático só ativa com senha
  confirmada, e `requiresManualApproval` é `true` sempre — inclusive depois
  de ativar o Modo Automático.
- Rota `/new-campaign` registrada em `app_routes.dart`/`app.dart`, ainda
  sem ponto de entrada real (a Home/Dashboard, §5, não existe nesta
  sandbox).

**Deliberadamente fora desta fatia** (sem dependência externa desnecessária,
por pedido explícito, em ambas as fatias): nenhuma chamada de rede real.
OAuth de canais, autenticação, reautenticação por senha de administrador, a
geração real de criativos via AI Gateway, e a integração com
`contracts/bff-openapi.yaml` ficam para uma camada de serviço/repositório
futura — os `TODO`s no código marcam exatamente onde. Nenhuma dependência de
terceiros foi adicionada ao `pubspec.yaml`: navegação usa
`Navigator`/rotas nativas do `MaterialApp`, estado usa `ChangeNotifier`
nativo (não `provider`/`riverpod`/`bloc`).

## Limitação de verificação, com transparência

O Flutter/Dart SDK **não está instalado nesta sandbox** — confirmado por
investigação direta (`which flutter`, `which dart`, checagem de `/opt` e
`snap`), consistente com o achado já registrado em
`docs/00_DIAGNOSTICO_INICIAL.md` ("Flutter / Dart | Ausentes"). Portanto:

- `flutter analyze` e `flutter test` **não foram executados de fato** sobre
  este código.
- Em vez disso, foi feita uma verificação estática manual: balanceamento de
  chaves/parênteses em todos os arquivos `.dart`, checagem cruzada de que
  todo `import` relativo resolve para um arquivo existente, e revisão
  específica de duas APIs sensíveis à versão do Flutter
  (`DropdownButtonFormField.value` em vez de `.initialValue`, que só existe a
  partir do Flutter 3.32; `ColorScheme.surfaceContainerHighest`, disponível
  desde o 3.22 — ambas compatíveis com o piso declarado em `pubspec.yaml`,
  `flutter: ">=3.22.0"`).
- **Isso não substitui a execução real.** Antes de aceitar este código como
  validado, rodar `flutter pub get && flutter analyze && flutter test` em um
  ambiente com o SDK — o PC do Diretor (Bloco C, conforme
  `docs/10_PLANO_AQUI_VS_PC.md`) é o candidato natural.

## Próximos passos sugeridos

1. Rodar `flutter analyze`/`flutter test` no PC do Diretor e corrigir
   qualquer divergência real encontrada.
2. Construir a camada de serviço/repositório que fala com o BFF/API real
   (autenticação, `POST /connections/oauth/start`, `POST /brand-profiles`,
   validação real de senha de administrador, geração de criativos via AI
   Gateway).
3. Construir a Home/Dashboard (§5) como ponto de entrada real para o fluxo
   de Nova Campanha (hoje só acessível via rota nomeada `/new-campaign`,
   sem botão/tela que a acione).
4. Conectar `ObjectiveAndChannelScreen.connectedChannels` ao estado real de
   conexões (hoje construído isoladamente no onboarding, sem persistência
   nem compartilhamento entre features).
5. Construir a tela de Detalhe da Campanha (§7) e o fluxo de aprovação em
   si (§6.5, ações Aprovar/Rejeitar/Solicitar Ajustes, restritas a usuário
   com permissão de aprovador — F10.3), que hoje é apenas o destino
   implícito do botão "Enviar para Aprovação".
