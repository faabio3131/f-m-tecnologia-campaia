/// Widget raiz do app CampaIA.
///
/// Nesta fatia (Fase 8, caminho critico), a unica rota real e' o
/// Onboarding -- a Home/Dashboard (secao 5 da especificacao) ainda nao foi
/// construida, entao a rota inicial aponta direto para o onboarding em vez
/// de para uma tela que nao existe.
library;

import 'package:flutter/material.dart';

import 'core/navigation/app_routes.dart';
import 'features/onboarding/screens/onboarding_flow_screen.dart';

class CampaiaApp extends StatelessWidget {
  const CampaiaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CampaIA',
      debugShowCheckedModeBanner: false,
      initialRoute: AppRoutes.onboarding,
      routes: {
        AppRoutes.onboarding: (context) => const OnboardingFlowScreen(),
      },
    );
  }
}
