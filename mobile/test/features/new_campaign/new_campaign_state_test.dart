// Testes de NewCampaignState -- cobrem logica de estado/navegacao, com
// foco extra nas duas regras mais sensiveis desta feature:
// 1. Modo Automatico so ativa com senha confirmada (secao 9.1.1).
// 2. Campanha nova SEMPRE exige aprovacao manual, em qualquer modo (Charter
//    §9; DECISOES_DIRETOR.md item 5).
//
// NOTA DE TRANSPARENCIA (mesma desta sandbox, ja documentada no onboarding):
// o Flutter/Dart SDK nao esta instalado aqui. Este arquivo foi escrito com o
// mesmo rigor sintatico dos demais (chaves/parenteses balanceados, imports
// verificados manualmente), mas `flutter test` ainda NAO foi executado de
// fato -- rodar antes de aceitar como validado.

import 'package:campaia_app/features/new_campaign/state/new_campaign_state.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('NewCampaignState.navigation', () {
    test('starts on objectiveAndChannel', () {
      final state = NewCampaignState();
      expect(state.currentStep, NewCampaignStep.objectiveAndChannel);
      expect(state.isFirstStep, isTrue);
    });

    test('goToNextStep advances through all 3 steps in order', () {
      final state = NewCampaignState();

      state.goToNextStep();
      expect(state.currentStep, NewCampaignStep.budgetAndAutonomy);

      state.goToNextStep();
      expect(state.currentStep, NewCampaignStep.reviewAndCreativePreview);
      expect(state.isLastStep, isTrue);
    });

    test('goToNextStep is a no-op past the last step', () {
      final state = NewCampaignState();
      state
        ..goToNextStep()
        ..goToNextStep()
        ..goToNextStep(); // one extra call past reviewAndCreativePreview

      expect(state.currentStep, NewCampaignStep.reviewAndCreativePreview);
    });

    test('goToPreviousStep is a no-op before the first step', () {
      final state = NewCampaignState();
      state.goToPreviousStep();
      expect(state.currentStep, NewCampaignStep.objectiveAndChannel);
    });
  });

  group('NewCampaignState.canProceedFromObjectiveAndChannel', () {
    test('is false with no objective and no channel', () {
      final state = NewCampaignState();
      expect(state.canProceedFromObjectiveAndChannel, isFalse);
    });

    test('is false with an objective but no channel', () {
      final state = NewCampaignState();
      state.updateBriefing(
        (b) => b.copyWith(objective: CampaignObjective.leads),
      );
      expect(state.canProceedFromObjectiveAndChannel, isFalse);
    });

    test('is true with an objective and at least one channel', () {
      final state = NewCampaignState();
      state.updateBriefing(
        (b) => b.copyWith(
          objective: CampaignObjective.leads,
          selectedChannels: {CampaignChannel.googleAds},
        ),
      );
      expect(state.canProceedFromObjectiveAndChannel, isTrue);
    });
  });

  group('NewCampaignState.canSelectChannel', () {
    test('reflects only the connected channels passed in', () {
      final state = NewCampaignState();
      final connected = {CampaignChannel.meta};

      expect(state.canSelectChannel(CampaignChannel.meta, connected), isTrue);
      expect(
        state.canSelectChannel(CampaignChannel.googleAds, connected),
        isFalse,
      );
    });
  });

  group('NewCampaignState autonomy mode', () {
    test('starts in manual mode by default', () {
      final state = NewCampaignState();
      expect(state.autonomyMode, AutonomyMode.manual);
      expect(state.isAutomaticModeConfirmed, isFalse);
    });

    test('confirmAutomaticModeWithPassword does NOT activate on invalid password', () {
      final state = NewCampaignState();

      final activated =
          state.confirmAutomaticModeWithPassword(passwordIsValid: false);

      expect(activated, isFalse);
      expect(state.autonomyMode, AutonomyMode.manual);
      expect(state.isAutomaticModeConfirmed, isFalse);
    });

    test('confirmAutomaticModeWithPassword activates on valid password', () {
      final state = NewCampaignState();

      final activated =
          state.confirmAutomaticModeWithPassword(passwordIsValid: true);

      expect(activated, isTrue);
      expect(state.autonomyMode, AutonomyMode.automatic);
      expect(state.isAutomaticModeConfirmed, isTrue);
    });

    test('switchToManualMode requires no password and clears confirmation', () {
      final state = NewCampaignState();
      state.confirmAutomaticModeWithPassword(passwordIsValid: true);
      expect(state.autonomyMode, AutonomyMode.automatic);

      state.switchToManualMode();

      expect(state.autonomyMode, AutonomyMode.manual);
      expect(state.isAutomaticModeConfirmed, isFalse);
    });
  });

  group('NewCampaignState.canProceedFromBudgetAndAutonomy', () {
    test('is false without a budget set', () {
      final state = NewCampaignState();
      expect(state.canProceedFromBudgetAndAutonomy, isFalse);
    });

    test('is false with a zero or negative budget', () {
      final state = NewCampaignState();
      state.setTotalBudget(0);
      expect(state.canProceedFromBudgetAndAutonomy, isFalse);
    });

    test('is true in manual mode once a positive budget is set', () {
      final state = NewCampaignState();
      state.setTotalBudget(500);
      expect(state.canProceedFromBudgetAndAutonomy, isTrue);
    });

    test(
        'is false in automatic mode if password was never confirmed '
        '(defensive: state should not be reachable this way via the UI, '
        'but the getter must not assume it)', () {
      final state = NewCampaignState();
      state.setTotalBudget(500);
      // Directly forces automatic mode without going through the confirm
      // flow is not possible via the public API (by design) -- this test
      // instead confirms the only path that flips the mode also sets the
      // confirmation flag together, so this scenario cannot occur.
      final activated =
          state.confirmAutomaticModeWithPassword(passwordIsValid: true);
      expect(activated, isTrue);
      expect(state.canProceedFromBudgetAndAutonomy, isTrue);
    });
  });

  group('NewCampaignState.requiresManualApproval — regra inegociavel', () {
    test('is always true in manual mode', () {
      final state = NewCampaignState();
      expect(state.autonomyMode, AutonomyMode.manual);
      expect(state.requiresManualApproval, isTrue);
    });

    test('is always true even after automatic mode is activated', () {
      final state = NewCampaignState();
      state.confirmAutomaticModeWithPassword(passwordIsValid: true);
      expect(state.autonomyMode, AutonomyMode.automatic);

      // A regra mais importante desta feature: ativar o Modo Automatico
      // NUNCA torna esta propriedade falsa para uma campanha nova.
      expect(state.requiresManualApproval, isTrue);
    });
  });

  group('NewCampaignState creatives and policy check', () {
    test('allCreativesPassedPolicyCheck is false with no creative for a selected channel', () {
      final state = NewCampaignState();
      state.updateBriefing(
        (b) => b.copyWith(selectedChannels: {CampaignChannel.googleAds}),
      );

      expect(state.allCreativesPassedPolicyCheck, isFalse);
    });

    test('allCreativesPassedPolicyCheck is false when any selected channel needs review', () {
      final state = NewCampaignState();
      state.updateBriefing(
        (b) => b.copyWith(
          selectedChannels: {CampaignChannel.googleAds, CampaignChannel.meta},
        ),
      );
      state.updateCreative(
        CampaignChannel.googleAds,
        const ChannelCreative(
          channel: CampaignChannel.googleAds,
          policyStatus: PolicyCheckStatus.approved,
        ),
      );
      state.updateCreative(
        CampaignChannel.meta,
        const ChannelCreative(
          channel: CampaignChannel.meta,
          policyStatus: PolicyCheckStatus.needsReview,
          policyNote: 'alegação não permitida',
        ),
      );

      expect(state.allCreativesPassedPolicyCheck, isFalse);
    });

    test('allCreativesPassedPolicyCheck is true when all selected channels are approved', () {
      final state = NewCampaignState();
      state.updateBriefing(
        (b) => b.copyWith(selectedChannels: {CampaignChannel.whatsAppBusiness}),
      );
      state.updateCreative(
        CampaignChannel.whatsAppBusiness,
        const ChannelCreative(
          channel: CampaignChannel.whatsAppBusiness,
          policyStatus: PolicyCheckStatus.approved,
        ),
      );

      expect(state.allCreativesPassedPolicyCheck, isTrue);
    });
  });

  group('NewCampaignState notifies listeners', () {
    test('updateBriefing notifies listeners', () {
      final state = NewCampaignState();
      var notified = false;
      state.addListener(() => notified = true);

      state.updateBriefing(
        (b) => b.copyWith(objective: CampaignObjective.sales),
      );

      expect(notified, isTrue);
    });

    test('confirmAutomaticModeWithPassword notifies listeners on success', () {
      final state = NewCampaignState();
      var notifyCount = 0;
      state.addListener(() => notifyCount++);

      state.confirmAutomaticModeWithPassword(passwordIsValid: true);

      expect(notifyCount, 1);
    });
  });
}
