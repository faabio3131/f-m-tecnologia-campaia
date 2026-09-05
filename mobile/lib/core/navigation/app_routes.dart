/// Nomes de rota de nivel superior do app.
///
/// So contem o que ja existe nesta fatia (Fase 8, caminho critico). Novas
/// rotas (Home, Nova Campanha, etc.) sao adicionadas quando essas telas
/// forem construidas -- nao antecipadas aqui, para nao inventar estrutura de
/// navegacao sem a tela que a justifique (ver mapa de navegacao, secao 2 da
/// especificacao).
library;

abstract final class AppRoutes {
  static const String onboarding = '/onboarding';
}
