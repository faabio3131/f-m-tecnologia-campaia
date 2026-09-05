/// Tela host do fluxo de Onboarding: hospeda as 4 etapas (secao 2 e 3 da
/// especificacao) e delega a navegacao entre elas para [OnboardingState].
///
/// Esta e' a unica tela registrada na rota de nivel superior ("/onboarding");
/// as 4 etapas internas nao tem rota propria -- elas trocam via
/// [OnboardingState.currentStep], nao via Navigator.push, porque sao passos
/// de um unico formulario multi-etapa, nao telas independentes que o usuario
/// deveria poder abrir por deep link isoladamente.
library;

import 'package:flutter/material.dart';

import '../state/onboarding_state.dart';
import '../widgets/onboarding_step_indicator.dart';
import 'business_unit_screen.dart';
import 'company_registration_screen.dart';
import 'connect_accounts_screen.dart';
import 'login_screen.dart';

class OnboardingFlowScreen extends StatefulWidget {
  const OnboardingFlowScreen({super.key, this.onOnboardingComplete});

  /// Chamado quando o usuario conclui o onboarding (canFinishOnboarding ==
  /// true e a acao "Concluir Onboarding" e' confirmada). A navegacao real
  /// para a Home (fora do escopo desta fatia) e' responsabilidade de quem
  /// constrói este widget, nao desta tela.
  final VoidCallback? onOnboardingComplete;

  @override
  State<OnboardingFlowScreen> createState() => _OnboardingFlowScreenState();
}

class _OnboardingFlowScreenState extends State<OnboardingFlowScreen> {
  late final OnboardingState _state;

  @override
  void initState() {
    super.initState();
    _state = OnboardingState();
  }

  @override
  void dispose() {
    _state.dispose();
    super.dispose();
  }

  Widget _buildCurrentStep() {
    switch (_state.currentStep) {
      case OnboardingStep.login:
        return LoginScreen(state: _state);
      case OnboardingStep.companyRegistration:
        return CompanyRegistrationScreen(state: _state);
      case OnboardingStep.businessUnit:
        return BusinessUnitScreen(state: _state);
      case OnboardingStep.connectAccounts:
        return ConnectAccountsScreen(
          state: _state,
          onFinish: widget.onOnboardingComplete,
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
            title: const Text('Bem-vindo ao CampaIA'),
            bottom: PreferredSize(
              preferredSize: const Size.fromHeight(8),
              child: OnboardingStepIndicator(currentStep: _state.currentStep),
            ),
          ),
          body: SafeArea(child: _buildCurrentStep()),
        );
      },
    );
  }
}
