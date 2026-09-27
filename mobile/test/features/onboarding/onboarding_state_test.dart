// Testes de OnboardingState -- cobrem apenas logica de estado/navegacao
// (sem renderizar widgets), ja que a regra mais sensivel desta fatia e'
// puramente logica: "Concluir Onboarding" so habilita com >=1 canal
// conectado (secao 3.4 da especificacao). Nao ha chamada de rede aqui para
// testar -- essa camada ainda nao existe, deliberadamente (ver comentario em
// connect_accounts_screen.dart).
//
// NOTA DE TRANSPARENCIA: o Flutter/Dart SDK nao esta disponivel nesta
// sandbox (confirmado via `which flutter`/`which dart`, ambos ausentes;
// coerente com docs/00_DIAGNOSTICO_INICIAL.md, que ja registrava
// "Flutter / Dart | Ausentes"). Este arquivo foi escrito com o mesmo rigor
// sintatico dos demais, mas `flutter test` ainda NAO foi executado de fato
// nesta sandbox -- rodar antes de aceitar como validado, no PC do Diretor ou
// em um ambiente com o SDK instalado.

import 'package:campaia_app/features/onboarding/state/onboarding_state.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('OnboardingState.navigation', () {
    test('starts on the login step', () {
      final state = OnboardingState();
      expect(state.currentStep, OnboardingStep.login);
      expect(state.isFirstStep, isTrue);
      expect(state.isLastStep, isFalse);
    });

    test('goToNextStep advances through all 4 steps in order', () {
      final state = OnboardingState();

      state.goToNextStep();
      expect(state.currentStep, OnboardingStep.companyRegistration);

      state.goToNextStep();
      expect(state.currentStep, OnboardingStep.businessUnit);

      state.goToNextStep();
      expect(state.currentStep, OnboardingStep.connectAccounts);
      expect(state.isLastStep, isTrue);
    });

    test('goToNextStep is a no-op past the last step', () {
      final state = OnboardingState();
      state
        ..goToNextStep()
        ..goToNextStep()
        ..goToNextStep()
        ..goToNextStep(); // called one extra time past connectAccounts

      expect(state.currentStep, OnboardingStep.connectAccounts);
    });

    test('goToPreviousStep is a no-op before the first step', () {
      final state = OnboardingState();
      state.goToPreviousStep();
      expect(state.currentStep, OnboardingStep.login);
    });

    test('skipBusinessUnit marks the step skipped and advances', () {
      final state = OnboardingState()
        ..goToNextStep()
        ..goToNextStep(); // now on businessUnit

      expect(state.businessUnitSkipped, isFalse);
      state.skipBusinessUnit();

      expect(state.businessUnitSkipped, isTrue);
      expect(state.currentStep, OnboardingStep.connectAccounts);
    });
  });

  group('OnboardingState.canFinishOnboarding', () {
    test('is false when no channel is connected', () {
      final state = OnboardingState();
      expect(state.canFinishOnboarding, isFalse);
    });

    test('is false when a channel errored but none connected', () {
      final state = OnboardingState();
      state.updateConnection(
        Channel.googleAds,
        const ChannelConnectionState(
          status: ConnectionStatus.error,
          errorMessage: 'timeout',
        ),
      );
      expect(state.canFinishOnboarding, isFalse);
    });

    test('is true as soon as exactly one channel is connected', () {
      final state = OnboardingState();
      state.updateConnection(
        Channel.whatsAppBusiness,
        const ChannelConnectionState(status: ConnectionStatus.connected),
      );
      expect(state.canFinishOnboarding, isTrue);
    });

    test('remains true when additional channels are also connected', () {
      final state = OnboardingState();
      state.updateConnection(
        Channel.googleAds,
        const ChannelConnectionState(status: ConnectionStatus.connected),
      );
      state.updateConnection(
        Channel.meta,
        const ChannelConnectionState(status: ConnectionStatus.connected),
      );
      expect(state.canFinishOnboarding, isTrue);
    });

    test('connectionFor returns notConnected default for untouched channel',
        () {
      final state = OnboardingState();
      expect(
        state.connectionFor(Channel.meta).status,
        ConnectionStatus.notConnected,
      );
    });
  });

  group('OnboardingState notifies listeners', () {
    test('updateConnection notifies listeners', () {
      final state = OnboardingState();
      var notified = false;
      state.addListener(() => notified = true);

      state.updateConnection(
        Channel.googleAds,
        const ChannelConnectionState(status: ConnectionStatus.connected),
      );

      expect(notified, isTrue);
    });

    test('goToNextStep notifies listeners', () {
      final state = OnboardingState();
      var notifyCount = 0;
      state.addListener(() => notifyCount++);

      state.goToNextStep();

      expect(notifyCount, 1);
    });
  });
}
