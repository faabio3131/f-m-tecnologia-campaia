/// Cartao de conexao de um unico canal (secao 3.4 da especificacao).
///
/// Cada canal (Google Ads, Meta, WhatsApp Business) e' independente: o
/// usuario pode conectar zero, um, dois ou os tres, e prosseguir com apenas
/// um conectado (decisao D-06: "cliente escolhe qual usar"). Este widget nao
/// sabe nada sobre OAuth de verdade -- ele apenas expoe um callback
/// [onConnectPressed] e renderiza o [ChannelConnectionState] que recebe. A
/// integracao real com POST /connections/oauth/start (ver
/// contracts/bff-openapi.yaml) fica para a camada de servico, fora desta
/// fatia.
library;

import 'package:flutter/material.dart';

import '../state/onboarding_state.dart';

class ChannelConnectionCard extends StatelessWidget {
  const ChannelConnectionCard({
    super.key,
    required this.title,
    required this.description,
    required this.state,
    required this.onConnectPressed,
  });

  final String title;
  final String description;
  final ChannelConnectionState state;
  final VoidCallback onConnectPressed;

  String get _statusLabel {
    switch (state.status) {
      case ConnectionStatus.notConnected:
        return 'Não conectado';
      case ConnectionStatus.connected:
        return 'Conectado';
      case ConnectionStatus.error:
        return 'Erro na conexão';
    }
  }

  @override
  Widget build(BuildContext context) {
    final bool isConnected = state.status == ConnectionStatus.connected;
    final bool hasError = state.status == ConnectionStatus.error;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    title,
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
                Text(
                  _statusLabel,
                  style: TextStyle(
                    color: isConnected
                        ? Colors.green
                        : (hasError ? Colors.red : Colors.grey),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(description),
            if (hasError && state.errorMessage != null) ...[
              const SizedBox(height: 4),
              Text(
                state.errorMessage!,
                style: const TextStyle(color: Colors.red),
              ),
            ],
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: isConnected ? null : onConnectPressed,
              child: Text(isConnected ? 'Conectado' : 'Conectar'),
            ),
          ],
        ),
      ),
    );
  }
}
