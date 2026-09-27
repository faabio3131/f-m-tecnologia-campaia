/// Indicador visual simples de progresso entre as 4 etapas do onboarding.
///
/// Deliberadamente minimalista (sem cores/tipografia de design system) --
/// a especificacao (secao 1) e' explicita que "este documento nao especifica
/// visual... design visual e' um bloco separado, a ser tratado apos validacao
/// desta especificacao funcional". Este widget existe para tornar a
/// navegacao testavel e legivel, nao para antecipar o visual final.
library;

import 'package:flutter/material.dart';

import '../state/onboarding_state.dart';

class OnboardingStepIndicator extends StatelessWidget {
  const OnboardingStepIndicator({super.key, required this.currentStep});

  final OnboardingStep currentStep;

  static const List<OnboardingStep> _steps = <OnboardingStep>[
    OnboardingStep.login,
    OnboardingStep.companyRegistration,
    OnboardingStep.businessUnit,
    OnboardingStep.connectAccounts,
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
