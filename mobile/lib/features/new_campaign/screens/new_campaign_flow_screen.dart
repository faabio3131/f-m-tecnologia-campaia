/// Tela host do fluxo de Nova Campanha: hospeda as 3 etapas do caminho
/// critico (Objetivo+Canal, Orcamento+Autonomia, Revisao+Previa do
/// Criativo) e delega a navegacao para [NewCampaignState].
///
/// Mesmo padrao estrutural de OnboardingFlowScreen: as etapas trocam via
/// estado (nao via Navigator.push), porque sao passos de um unico fluxo
/// multi-etapa, nao telas independentes.
library;

import 'package:flutter/material.dart';

import '../state/new_campaign_state.dart';
import '../widgets/new_campaign_step_indicator.dart';
import 'budget_and_autonomy_screen.dart';
import 'objective_and_channel_screen.dart';
import 'review_and_creative_preview_screen.dart';

class NewCampaignFlowScreen extends StatefulWidget {
  const NewCampaignFlowScreen({super.key, this.onCampaignSubmittedForApproval});

  /// Chamado quando o usuario envia a campanha para aprovacao (secao 6.5).
  /// Esta fatia nao publica nada sozinha -- toda campanha nova sempre
  /// exige aprovacao humana explicita (ver
  /// NewCampaignState.requiresManualApproval), entao este callback
  /// representa exatamente isso: "enviar para a fila de aprovacao", nunca
  /// "publicar".
  final VoidCallback? onCampaignSubmittedForApproval;

  @override
  State<NewCampaignFlowScreen> createState() => _NewCampaignFlowScreenState();
}

class _NewCampaignFlowScreenState extends State<NewCampaignFlowScreen> {
  late final NewCampaignState _state;

  @override
  void initState() {
    super.initState();
    _state = NewCampaignState();
  }

  @override
  void dispose() {
    _state.dispose();
    super.dispose();
  }

  Widget _buildCurrentStep() {
    switch (_state.currentStep) {
      case NewCampaignStep.objectiveAndChannel:
        return ObjectiveAndChannelScreen(state: _state);
      case NewCampaignStep.budgetAndAutonomy:
        return BudgetAndAutonomyScreen(state: _state);
      case NewCampaignStep.reviewAndCreativePreview:
        return ReviewAndCreativePreviewScreen(
          state: _state,
          onSubmitForApproval: widget.onCampaignSubmittedForApproval,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _state,
      builder: (context, _) {
        return Scaffold(
          appBar: AppBar(
            automaticallyImplyLeading: !_state.isFirstStep,
            title: const Text('Nova Campanha'),
            bottom: PreferredSize(
              preferredSize: const Size.fromHeight(8),
              child: NewCampaignStepIndicator(currentStep: _state.currentStep),
            ),
          ),
          body: SafeArea(child: _buildCurrentStep()),
        );
      },
    );
  }
}
