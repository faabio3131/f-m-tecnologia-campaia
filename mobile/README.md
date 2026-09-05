# CampaIA — App Mobile (Flutter)

Fase 8 do painel de execução (`backend/01_PAINEL_EXECUCAO_v18_VIGENTE.md`).
Stack: Flutter + Dart (decisão já registrada em `docs/05_ARQUITETURA_V2.md`
§6, `docs/product/NON_FUNCTIONAL_REQUIREMENTS.md` §8.1 e
`docs/10_PLANO_AQUI_VS_PC.md`, bloco C6).

## Estado desta fatia (05/09/2026)

Primeiro passo do caminho crítico recomendado no painel v18: a tela de
**Onboarding** (F1.1–F1.5), especificada em
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

**Deliberadamente fora desta fatia** (sem dependência externa desnecessária,
por pedido explícito): nenhuma chamada de rede real. OAuth de canais,
autenticação, e a integração com `contracts/bff-openapi.yaml` (`POST
/connections/oauth/start`, etc.) ficam para uma camada de
serviço/repositório futura — os `TODO`s no código marcam exatamente onde.
Nenhuma dependência de terceiros foi adicionada ao `pubspec.yaml`: navegação
usa `Navigator`/rotas nativas do `MaterialApp`, estado usa `ChangeNotifier`
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
   (autenticação, `POST /connections/oauth/start`, `POST /brand-profiles`).
3. Seguir para a próxima tela do caminho crítico: Home/Dashboard (§5) e o
   fluxo de Nova Campanha (§6), que é o pré-requisito para qualquer campanha
   poder ser criada pelo app.
