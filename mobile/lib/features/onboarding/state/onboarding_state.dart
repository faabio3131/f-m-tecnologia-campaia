/// Estado do fluxo de Onboarding (F1.1-F1.5).
///
/// Fonte da verdade funcional: docs/product/13_ESPECIFICACAO_TELAS_APP.md, secao 3.
/// Nao adiciona nenhuma regra alem do que ja foi especificado e aprovado -- em
/// particular, nao assume nenhum vertical de negocio especifico (decisao D-03:
/// "qualquer pequeno negocio local"), e nao inclui nenhum canal alem de
/// Google Ads, Meta e WhatsApp Business (fora de escopo: outros canais).
library;

import 'package:flutter/foundation.dart';

/// As 4 etapas do onboarding, na ordem do mapa de navegacao (secao 2 da
/// especificacao). `login` cobre a tela "Criar Conta / Login" (3.1).
enum OnboardingStep {
  login,
  companyRegistration,
  businessUnit,
  connectAccounts,
}

/// Estado de conexao de um canal individual (secao 3.4).
enum ConnectionStatus { notConnected, connected, error }

/// Os 3 canais oferecidos no MVP (secao 3.4). Nenhum outro canal e' valido
/// aqui -- adicionar um novo canal exige atualizar a especificacao primeiro.
enum Channel { googleAds, meta, whatsAppBusiness }

/// Tipos de negocio genericos (secao 3.2) -- deliberadamente sem nenhuma
/// opcao especifica de vertical (ex: "restaurante"), por forca da D-03.
enum BusinessType { ecommerce, services, saas, realEstate, physicalRetail, other }

@immutable
class ChannelConnectionState {
  const ChannelConnectionState({
    this.status = ConnectionStatus.notConnected,
    this.selectedAccountId,
    this.errorMessage,
  });

  final ConnectionStatus status;

  /// Preenchido apos OAuth bem-sucedido e selecao de conta (Google Ads /
  /// Meta Ad Account) -- secao 3.4. Nulo para WhatsApp, que usa numero
  /// comercial em vez de selecao de conta.
  final String? selectedAccountId;

  final String? errorMessage;

  ChannelConnectionState copyWith({
    ConnectionStatus? status,
    String? selectedAccountId,
    String? errorMessage,
  }) {
    return ChannelConnectionState(
      status: status ?? this.status,
      selectedAccountId: selectedAccountId ?? this.selectedAccountId,
      errorMessage: errorMessage,
    );
  }
}

/// Estado completo do fluxo de onboarding.
///
/// Deliberadamente sem nenhuma chamada de rede aqui -- esta classe so guarda
/// estado local de navegacao e formulario. A integracao real com o BFF/API
/// (POST /brand-profiles, POST /connections/oauth/start, etc. -- ver
/// contracts/bff-openapi.yaml) e' responsabilidade de uma camada de
/// repositorio/servico que ainda nao existe nesta fatia, propositalmente:
/// o pedido desta etapa foi apenas a estrutura inicial de pastas/widgets e
/// estados de navegacao, sem dependencias externas desnecessarias.
class OnboardingState extends ChangeNotifier {
  OnboardingState()
      : _currentStep = OnboardingStep.login,
        _channels = {
          Channel.googleAds: const ChannelConnectionState(),
          Channel.meta: const ChannelConnectionState(),
          Channel.whatsAppBusiness: const ChannelConnectionState(),
        };

  OnboardingStep _currentStep;
  OnboardingStep get currentStep => _currentStep;

  // --- 3.2 Cadastro da Empresa (F1.1) ---
  String companyName = '';
  String cnpj = '';
  BusinessType? businessType;
  String language = 'pt-BR';

  // --- 3.3 Unidade de Negocio (F1.2) ---
  String businessUnitName = '';
  String businessUnitAddress = '';
  bool businessUnitSkipped = false;

  // --- 3.4 Conectar Contas (F1.3, F1.4, F1.5) ---
  final Map<Channel, ChannelConnectionState> _channels;

  ChannelConnectionState connectionFor(Channel channel) =>
      _channels[channel] ?? const ChannelConnectionState();

  /// Reflete literalmente a regra da secao 3.4: "Concluir Onboarding
  /// habilitada assim que pelo menos um canal estiver conectado."
  bool get canFinishOnboarding => _channels.values
      .any((state) => state.status == ConnectionStatus.connected);

  void updateConnection(Channel channel, ChannelConnectionState newState) {
    _channels[channel] = newState;
    notifyListeners();
  }

  // --- Navegacao linear entre as 4 etapas ---

  static const List<OnboardingStep> _order = <OnboardingStep>[
    OnboardingStep.login,
    OnboardingStep.companyRegistration,
    OnboardingStep.businessUnit,
    OnboardingStep.connectAccounts,
  ];

  bool get isFirstStep => _currentStep == _order.first;
  bool get isLastStep => _currentStep == _order.last;

  void goToNextStep() {
    final int index = _order.indexOf(_currentStep);
    if (index < _order.length - 1) {
      _currentStep = _order[index + 1];
      notifyListeners();
    }
  }

  void goToPreviousStep() {
    final int index = _order.indexOf(_currentStep);
    if (index > 0) {
      _currentStep = _order[index - 1];
      notifyListeners();
    }
  }

  /// Secao 3.3: a Unidade de Negocio "pode ser pulada com 'Adicionar
  /// depois'". Pular nao apaga dados ja digitados, apenas marca a etapa
  /// como intencionalmente incompleta.
  void skipBusinessUnit() {
    businessUnitSkipped = true;
    goToNextStep();
  }
}
