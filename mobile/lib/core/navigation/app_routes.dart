/// Nomes de rota de nivel superior do app.
///
/// So contem o que ja existe nesta fatia (Fase 8, caminho critico). Novas
/// rotas (Home, etc.) sao adicionadas quando essas telas forem construidas
/// -- nao antecipadas aqui, para nao inventar estrutura de navegacao sem a
/// tela que a justifique (ver mapa de navegacao, secao 2 da especificacao).
library;

abstract final class AppRoutes {
  static const String onboarding = '/onboarding';

  /// Fluxo de Nova Campanha (secao 6). Ainda sem um ponto real de entrada a
  /// partir de uma Home -- a Home/Dashboard (secao 5) nao foi construida
  /// nesta sandbox. A rota existe para que a tela seja navegavel assim que
  /// a Home (ou outro ponto de entrada) for construida, sem precisar
  /// registrar rota nesse momento.
  static const String newCampaign = '/new-campaign';
}
