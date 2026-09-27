/// Tela 3.4 (secao 3.4 da especificacao): Conectar Contas (F1.3, F1.4, F1.5).
///
/// Tres cartoes independentes, cada um com estado proprio (Nao conectado /
/// Conectado / Erro). "Concluir Onboarding" habilitada assim que pelo menos
/// um canal estiver conectado -- ver [OnboardingState.canFinishOnboarding],
/// que e' a fonte unica de verdade dessa regra (nao reimplementada aqui).
library;

import 'package:flutter/material.dart';

import '../state/onboarding_state.dart';
import '../widgets/channel_connection_card.dart';

class ConnectAccountsScreen extends StatelessWidget {
  const ConnectAccountsScreen({
    super.key,
    required this.state,
    this.onFinish,
  });

  final OnboardingState state;
  final VoidCallback? onFinish;

  /// Placeholder de conexao: marca o canal como conectado imediatamente.
  ///
  /// TODO(F1.3-F1.5): substituir por fluxo OAuth 2.0 real via
  /// POST /connections/oauth/start (contracts/bff-openapi.yaml) quando a
  /// camada de servico/repositorio for construida. Esta fatia cobre apenas
  /// estrutura de navegacao e estado, sem nenhuma chamada de rede --
  /// pedido explicito desta etapa ("sem dependencias externas
  /// desnecessarias").
  void _connect(Channel channel) {
    state.updateConnection(
      channel,
      state.connectionFor(channel).copyWith(
            status: ConnectionStatus.connected,
          ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: state,
      builder: (context, _) {
        return Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Conecte suas contas',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 4),
              const Text(
                'Conecte pelo menos um canal para continuar. Você pode '
                'conectar os demais depois.',
              ),
              const SizedBox(height: 16),
              Expanded(
                child: ListView(
                  children: [
                    ChannelConnectionCard(
                      title: 'Google Ads',
                      description:
                          'Inicia OAuth 2.0 e lista suas contas do Google Ads '
                          'para seleção.',
                      state: state.connectionFor(Channel.googleAds),
                      onConnectPressed: () => _connect(Channel.googleAds),
                    ),
                    const SizedBox(height: 12),
                    ChannelConnectionCard(
                      title: 'Meta (Facebook/Instagram)',
                      description:
                          'Inicia OAuth 2.0 e lista suas Ad Accounts do Meta '
                          'Business para seleção.',
                      state: state.connectionFor(Channel.meta),
                      onConnectPressed: () => _connect(Channel.meta),
                    ),
                    const SizedBox(height: 12),
                    ChannelConnectionCard(
                      title: 'WhatsApp Business',
                      description:
                          'Requer número comercial e aceite de permissões.',
                      state: state.connectionFor(Channel.whatsAppBusiness),
                      onConnectPressed: () =>
                          _connect(Channel.whatsAppBusiness),
                    ),
                  ],
                ),
              ),
              Row(
                children: [
                  TextButton(
                    onPressed: state.goToPreviousStep,
                    child: const Text('Voltar'),
                  ),
                  const Spacer(),
                  FilledButton(
                    onPressed: state.canFinishOnboarding ? onFinish : null,
                    child: const Text('Concluir Onboarding'),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }
}
