/// Indicador visual de progresso entre as 3 etapas do fluxo de Nova
/// Campanha. Mesmo padrao minimalista de OnboardingStepIndicator -- sem
/// cores/tipografia de design system (secao 1 da especificacao: visual e'
/// um bloco separado).
library;

import 'package:flutter/material.dart';

import '../state/new_campaign_state.dart';

class NewCampaignStepIndicator extends StatelessWidget {
  const NewCampaignStepIndicator({super.key, required this.currentStep});

  final NewCampaignStep currentStep;

  static const List<NewCampaignStep> _steps = <NewCampaignStep>[
    NewCampaignStep.objectiveAndChannel,
    NewCampaignStep.budgetAndAutonomy,
    NewCampaignStep.reviewAndCreativePreview,
  ];

  @override
  Widget build(BuildContext context) {
    final int currentIndex = _steps.indexOf(currentStep);
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        for (int i = 0; i < _steps.length; i++)
          Expanded(
            child: Container(
              key: ValueKey<int>(i),
              height: 4,
              margin: const EdgeInsets.symmetric(horizontal: 2),
              color: i <= currentIndex
                  ? Theme.of(context).colorScheme.primary
                  : Theme.of(context).colorScheme.surfaceContainerHighest,
            ),
          ),
      ],
    );
  }
}
