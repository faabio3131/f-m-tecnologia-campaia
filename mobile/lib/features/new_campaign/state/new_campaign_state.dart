/// Estado do fluxo de Nova Campanha.
///
/// Fonte da verdade funcional: docs/product/13_ESPECIFICACAO_TELAS_APP.md,
/// secoes 6 (Fluxo de Nova Campanha) e 9.1/9.1.1 (Autonomia). Esta fatia
/// cobre o caminho critico em 3 telas (pedido explicito desta etapa):
/// Objetivo+Canal, Orcamento+Autonomia, Revisao+Previa do Criativo -- uma
/// consolidacao das 5 etapas completas da especificacao (Briefing,
/// Estrategia, Criativos, Previa, Aprovacao), nao uma tela nova nao prevista.
/// Nenhum campo aqui reflete "F3.2 briefing conversacional por chat" (Fase
/// 2, fora de escopo) nem "F7.4 alertas automaticos" -- essas permanecem
/// fora do MVP.
///
/// Regra mais sensivel desta fatia, tratada com o mesmo cuidado que a
/// especificacao exige (Charter §9, DECISOES_DIRETOR.md item 5): campanha
/// **nova** sempre exige aprovacao humana antes de publicar, em qualquer
/// modo de autonomia. O Modo Automatico (Nivel 2) nunca aparece aqui como
/// uma forma de pular a aprovacao desta campanha -- ele so existe, na
/// especificacao, para otimizar campanhas ja aprovadas anteriormente (ver
/// AutonomyMode e o comentario em [NewCampaignState.requiresManualApproval]).
library;

import 'package:flutter/foundation.dart';

/// Objetivo primario da campanha (secao 6.1). Ordem reflete a prioridade da
/// D-04 quando o usuario nao especifica: Leads > Vendas > Visitas >
/// Mensagens.
enum CampaignObjective { leads, sales, visits, messages }

/// Os mesmos 3 canais do onboarding (secao 3.4) -- nenhum canal novo e'
/// introduzido aqui. Reutiliza os nomes conceituais, mas como um enum
/// proprio desta feature para nao acoplar new_campaign a onboarding.
enum CampaignChannel { googleAds, meta, whatsAppBusiness }

/// Nivel de autonomia configurado para a CONTA (nao para esta campanha
/// especifica) -- secao 9.1. So existem 2 opcoes reais no MVP; Niveis 0 e 3
/// aparecem desabilitados na tela de Configuracoes (fora desta fatia) e nao
/// sao modelados aqui porque uma campanha nunca pode ser criada sob eles.
enum AutonomyMode {
  /// Nivel 1 -- "Toda campanha passa por sua aprovacao antes de publicar."
  /// Selecionado por padrao para novas contas.
  manual,

  /// Nivel 2 -- otimizacao automatica de campanhas JA aprovadas, dentro de
  /// um teto definido pelo cliente e ativado com senha de administrador
  /// (secao 9.1.1). Nunca cobre a publicacao inicial de uma campanha nova.
  automatic,
}

@immutable
class BriefingData {
  const BriefingData({
    this.objective,
    this.secondaryObjectives = const <CampaignObjective>{},
    this.offerDescription = '',
    this.targetAudience = '',
    this.region = '',
    this.totalBudget,
    this.startDate,
    this.endDate,
    this.selectedChannels = const <CampaignChannel>{},
  });

  final CampaignObjective? objective;
  final Set<CampaignObjective> secondaryObjectives;
  final String offerDescription;
  final String targetAudience;
  final String region;
  final double? totalBudget;
  final DateTime? startDate;
  final DateTime? endDate;
  final Set<CampaignChannel> selectedChannels;

  BriefingData copyWith({
    CampaignObjective? objective,
    Set<CampaignObjective>? secondaryObjectives,
    String? offerDescription,
    String? targetAudience,
    String? region,
    double? totalBudget,
    DateTime? startDate,
    DateTime? endDate,
    Set<CampaignChannel>? selectedChannels,
  }) {
    return BriefingData(
      objective: objective ?? this.objective,
      secondaryObjectives: secondaryObjectives ?? this.secondaryObjectives,
      offerDescription: offerDescription ?? this.offerDescription,
      targetAudience: targetAudience ?? this.targetAudience,
      region: region ?? this.region,
      totalBudget: totalBudget ?? this.totalBudget,
      startDate: startDate ?? this.startDate,
      endDate: endDate ?? this.endDate,
      selectedChannels: selectedChannels ?? this.selectedChannels,
    );
  }
}

/// Limites do Modo Automatico (secao 9.1.1, Passo 1) -- so tem sentido
/// quando [NewCampaignState.autonomyMode] == [AutonomyMode.automatic]. Estes
/// limites sao configuracao DA CONTA (persistem entre campanhas), mas o
/// fluxo de nova campanha precisa deles para decidir se uma sugestao de
/// ajuste desta campanha, no futuro, poderia cair sob o automatico -- a
/// publicacao inicial em si nunca e' afetada por eles (ver
/// [NewCampaignState.requiresManualApproval]).
@immutable
class AutonomyLimits {
  const AutonomyLimits({
    this.dailyBudgetCap,
    this.monthlyBudgetCap,
    this.maxAdjustmentPercent = 10,
  });

  final double? dailyBudgetCap;
  final double? monthlyBudgetCap;

  /// Variacao percentual maxima permitida em ajustes automaticos (secao
  /// 9.1.1). Exemplo do documento: "ajustar lances em ate 10%".
  final double maxAdjustmentPercent;

  AutonomyLimits copyWith({
    double? dailyBudgetCap,
    double? monthlyBudgetCap,
    double? maxAdjustmentPercent,
  }) {
    return AutonomyLimits(
      dailyBudgetCap: dailyBudgetCap ?? this.dailyBudgetCap,
      monthlyBudgetCap: monthlyBudgetCap ?? this.monthlyBudgetCap,
      maxAdjustmentPercent: maxAdjustmentPercent ?? this.maxAdjustmentPercent,
    );
  }
}

/// Estado de geracao/revisao de um criativo, por canal (secao 6.3-6.4).
///
/// Nesta fatia nao ha chamada real ao AI Gateway -- os campos de texto e
/// imagem sao preenchidos por uma camada de servico futura (mesma decisao
/// deliberada do onboarding: sem dependencia externa nesta etapa). O que
/// existe aqui e' a estrutura que representa o resultado, para a tela de
/// Revisao poder renderizar algo real quando essa integracao existir.
enum PolicyCheckStatus { pending, approved, needsReview }

@immutable
class CreativeVariant {
  const CreativeVariant({
    required this.id,
    this.headline = '',
    this.description = '',
    this.callToAction = '',
    this.imageFormats = const <String>[],
  });

  final String id;
  final String headline;
  final String description;
  final String callToAction;

  /// Formatos de imagem ja gerados para esta variacao (ex: "quadrada",
  /// "story", "vertical_9x16") -- secao 6.3: "gerado automaticamente em
  /// todos os formatos relevantes do canal selecionado".
  final List<String> imageFormats;
}

@immutable
class ChannelCreative {
  const ChannelCreative({
    required this.channel,
    this.variants = const <CreativeVariant>[],
    this.policyStatus = PolicyCheckStatus.pending,
    this.policyNote,
  });

  final CampaignChannel channel;
  final List<CreativeVariant> variants;
  final PolicyCheckStatus policyStatus;

  /// Motivo do aviso de politica, quando policyStatus != approved (secao
  /// 6.3: selo "Aprovado pela politica" ou aviso "Revisar: [motivo]").
  final String? policyNote;

  ChannelCreative copyWith({
    List<CreativeVariant>? variants,
    PolicyCheckStatus? policyStatus,
    String? policyNote,
  }) {
    return ChannelCreative(
      channel: channel,
      variants: variants ?? this.variants,
      policyStatus: policyStatus ?? this.policyStatus,
      policyNote: policyNote ?? this.policyNote,
    );
  }
}

/// As 3 telas do caminho critico desta fatia, na ordem pedida.
enum NewCampaignStep {
  objectiveAndChannel,
  budgetAndAutonomy,
  reviewAndCreativePreview,
}

class NewCampaignState extends ChangeNotifier {
  NewCampaignState()
      : _currentStep = NewCampaignStep.objectiveAndChannel,
        _briefing = const BriefingData(),
        _autonomyMode = AutonomyMode.manual,
        _autonomyLimits = const AutonomyLimits(),
        _creativesByChannel = <CampaignChannel, ChannelCreative>{};

  NewCampaignStep _currentStep;
  NewCampaignStep get currentStep => _currentStep;

  static const List<NewCampaignStep> _order = <NewCampaignStep>[
    NewCampaignStep.objectiveAndChannel,
    NewCampaignStep.budgetAndAutonomy,
    NewCampaignStep.reviewAndCreativePreview,
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

  // --- Tela 1: Objetivo e Canal (secao 6.1, campos de objetivo/canal) ---

  BriefingData _briefing;
  BriefingData get briefing => _briefing;

  void updateBriefing(BriefingData Function(BriefingData current) update) {
    _briefing = update(_briefing);
    notifyListeners();
  }

  /// Reflete a regra da secao 6.1: um canal so pode ser selecionado se ja
  /// estiver conectado (ver onboarding). A lista de canais conectados vem
  /// de fora (da camada de conexoes/contas), nao e' responsabilidade deste
  /// estado guardar -- este metodo apenas aplica a regra dado o conjunto.
  bool canSelectChannel(CampaignChannel channel, Set<CampaignChannel> connectedChannels) {
    return connectedChannels.contains(channel);
  }

  bool get canProceedFromObjectiveAndChannel =>
      _briefing.objective != null && _briefing.selectedChannels.isNotEmpty;

  // --- Tela 2: Orcamento e Regra de Autonomia (secao 6.1 orcamento + 9.1) ---

  AutonomyMode _autonomyMode;
  AutonomyMode get autonomyMode => _autonomyMode;

  AutonomyLimits _autonomyLimits;
  AutonomyLimits get autonomyLimits => _autonomyLimits;

  /// Confirmacao de senha de administrador (secao 9.1.1, Passo 3) --
  /// necessaria apenas para ATIVAR o Modo Automatico. Nunca persistida como
  /// texto puro em nenhum outro campo deste estado; usada apenas no momento
  /// da chamada (que ainda nao existe nesta fatia) e descartada.
  bool _automaticModeConfirmedByPassword = false;
  bool get isAutomaticModeConfirmed => _automaticModeConfirmedByPassword;

  void setTotalBudget(double amount) {
    updateBriefing((current) => current.copyWith(totalBudget: amount));
  }

  void setAutonomyLimits(AutonomyLimits limits) {
    _autonomyLimits = limits;
    notifyListeners();
  }

  /// Troca Automatico -> Manual e' imediata, sem senha (secao 9.1: "so
  /// ativar automacao exige [senha], desativar nao precisa dessa
  /// friccao"). Troca Manual -> Automatico exige confirmacao explicita via
  /// [confirmAutomaticModeWithPassword] -- nao existe um setter direto para
  /// isso, de proposito, para que seja impossivel ativar o Modo Automatico
  /// sem passar pelo fluxo de senha.
  void switchToManualMode() {
    _autonomyMode = AutonomyMode.manual;
    _automaticModeConfirmedByPassword = false;
    notifyListeners();
  }

  /// Secao 9.1.1, Passo 3: so ativa o Modo Automatico se [passwordIsValid]
  /// for verdadeiro. A validacao real da senha (chamada ao backend) fica
  /// fora deste estado -- ele so guarda o RESULTADO da validacao, nunca a
  /// senha em si. Retorna se a ativacao ocorreu.
  bool confirmAutomaticModeWithPassword({required bool passwordIsValid}) {
    if (!passwordIsValid) {
      return false;
    }
    _autonomyMode = AutonomyMode.automatic;
    _automaticModeConfirmedByPassword = true;
    notifyListeners();
    return true;
  }

  bool get canProceedFromBudgetAndAutonomy {
    final bool hasBudget =
        _briefing.totalBudget != null && _briefing.totalBudget! > 0;
    if (!hasBudget) return false;
    if (_autonomyMode == AutonomyMode.automatic) {
      // Nao pode avancar em Modo Automatico "pela metade" -- ou a senha foi
      // confirmada, ou o modo deveria ter voltado para manual.
      return _automaticModeConfirmedByPassword;
    }
    return true;
  }

  // --- Tela 3: Revisao e Previa do Criativo (secoes 6.3, 6.4, 6.5) ---

  final Map<CampaignChannel, ChannelCreative> _creativesByChannel;

  ChannelCreative? creativeFor(CampaignChannel channel) =>
      _creativesByChannel[channel];

  void updateCreative(CampaignChannel channel, ChannelCreative creative) {
    _creativesByChannel[channel] = creative;
    notifyListeners();
  }

  /// Secao 6.3: um selo amarelo/vermelho de politica "bloqueia avanco ate o
  /// usuario resolver ou confirmar ciencia". Aqui simplificado como: nenhum
  /// canal selecionado pode estar com policyStatus == needsReview sem que o
  /// usuario ja tenha revisado (a UI decide como marcar "resolvido" --
  /// este getter so reflete o estado agregado).
  bool get allCreativesPassedPolicyCheck {
    for (final channel in _briefing.selectedChannels) {
      final creative = _creativesByChannel[channel];
      if (creative == null) return false;
      if (creative.policyStatus == PolicyCheckStatus.needsReview) {
        return false;
      }
    }
    return true;
  }

  /// **A regra mais importante desta fatia** (Charter §9, item 1;
  /// DECISOES_DIRETOR.md item 5, secao "Esclarecimento adicional"; secao
  /// 6.5 e' explicita: "nenhuma publicacao acontece sem essa etapa").
  ///
  /// Sempre retorna `true` para uma campanha NOVA (o unico tipo de campanha
  /// que este estado representa), independentemente de [autonomyMode]. O
  /// Modo Automatico (Nivel 2) nunca torna esta propriedade falsa -- ele so
  /// se aplica a otimizacoes de campanhas ja aprovadas anteriormente, um
  /// fluxo inteiramente fora desta feature (ver secao 8, "Sugestoes de
  /// Otimizacao", acessivel a partir do Detalhe da Campanha, nao daqui).
  /// Este getter existe deliberadamente, mesmo sendo sempre `true`, para
  /// que nenhuma tela desta feature precise "lembrar" a regra sozinha --
  /// ela pergunta aqui, e a resposta nunca muda por engano.
  bool get requiresManualApproval => true;
}
