/// Tela 1 do fluxo de Nova Campanha: Objetivo e Canal.
///
/// Consolida os campos de objetivo e de selecao de canal da Etapa 1 -
/// Briefing (secao 6.1 da especificacao). Os demais campos do briefing
/// completo (oferta/produto, publico-alvo, regiao, upload de materiais)
/// pertencem a uma tela de Briefing mais ampla, fora do escopo desta
/// fatia -- o pedido desta etapa foi especificamente "Selecao de Objetivo e
/// Canal", nao o formulario de briefing inteiro.
///
/// Regra da secao 6.1 preservada: "so aparecem os canais ja conectados no
/// onboarding; um canal nao conectado aparece desabilitado com link para
/// conectá-lo." Como a integracao real com o estado de conexoes (do
/// onboarding) ainda nao existe nesta fatia, [connectedChannels] e'
/// recebido via construtor com um default vazio -- quem constrói esta tela
/// no futuro (a partir do estado real de conexoes) passa o conjunto
/// correto; por ora, todos os canais aparecem desabilitados ate essa
/// integracao existir, em vez de assumir falsamente que estao conectados.
library;

import 'package:flutter/material.dart';

import '../state/new_campaign_state.dart';

class ObjectiveAndChannelScreen extends StatefulWidget {
  const ObjectiveAndChannelScreen({
    super.key,
    required this.state,
    this.connectedChannels = const <CampaignChannel>{},
  });

  final NewCampaignState state;

  /// Canais ja conectados (ver onboarding, secao 3.4). Vazio por padrao ate
  /// a integracao real com o estado de conexoes ser construida.
  final Set<CampaignChannel> connectedChannels;

  @override
  State<ObjectiveAndChannelScreen> createState() =>
      _ObjectiveAndChannelScreenState();
}

class _ObjectiveAndChannelScreenState
    extends State<ObjectiveAndChannelScreen> {
  static const Map<CampaignObjective, String> _objectiveLabels = {
    CampaignObjective.leads: 'Leads',
    CampaignObjective.sales: 'Vendas',
    CampaignObjective.visits: 'Visitas',
    CampaignObjective.messages: 'Mensagens',
  };

  static const Map<CampaignChannel, String> _channelLabels = {
    CampaignChannel.googleAds: 'Google Ads',
    CampaignChannel.meta: 'Meta (Facebook/Instagram)',
    CampaignChannel.whatsAppBusiness: 'WhatsApp Business',
  };

  void _selectObjective(CampaignObjective objective) {
    widget.state.updateBriefing(
      (current) => current.copyWith(objective: objective),
    );
  }

  void _toggleSecondaryObjective(CampaignObjective objective, bool selected) {
    widget.state.updateBriefing((current) {
      final updated = Set<CampaignObjective>.from(current.secondaryObjectives);
      if (selected) {
        updated.add(objective);
      } else {
        updated.remove(objective);
      }
      return current.copyWith(secondaryObjectives: updated);
    });
  }

  void _toggleChannel(CampaignChannel channel, bool selected) {
    widget.state.updateBriefing((current) {
      final updated = Set<CampaignChannel>.from(current.selectedChannels);
      if (selected) {
        updated.add(channel);
      } else {
        updated.remove(channel);
      }
      return current.copyWith(selectedChannels: updated);
    });
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.state,
      builder: (context, _) {
        final briefing = widget.state.briefing;
        return Padding(
          padding: const EdgeInsets.all(24),
          child: ListView(
            children: [
              const Text(
                'Qual é o objetivo desta campanha?',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 4),
              const Text('Objetivo primário — obrigatório.'),
              const SizedBox(height: 12),
              for (final entry in _objectiveLabels.entries)
                RadioListTile<CampaignObjective>(
                  title: Text(entry.value),
                  value: entry.key,
                  groupValue: briefing.objective,
                  onChanged: (value) {
                    if (value != null) _selectObjective(value);
                  },
                ),
              const SizedBox(height: 8),
              const Text(
                'Objetivos secundários (opcional)',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              for (final entry in _objectiveLabels.entries)
                if (entry.key != briefing.objective)
                  CheckboxListTile(
                    title: Text(entry.value),
                    value: briefing.secondaryObjectives.contains(entry.key),
                    onChanged: (selected) => _toggleSecondaryObjective(
                      entry.key,
                      selected ?? false,
                    ),
                  ),
              const SizedBox(height: 24),
              const Text(
                'Quais canais você quer usar?',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 4),
              const Text(
                'Apenas canais já conectados podem ser selecionados.',
              ),
              const SizedBox(height: 12),
              for (final entry in _channelLabels.entries)
                _ChannelTile(
                  label: entry.value,
                  isConnected: widget.connectedChannels.contains(entry.key),
                  isSelected: briefing.selectedChannels.contains(entry.key),
                  onChanged: (selected) => _toggleChannel(entry.key, selected),
                ),
              const SizedBox(height: 32),
              FilledButton(
                onPressed: widget.state.canProceedFromObjectiveAndChannel
                    ? widget.state.goToNextStep
                    : null,
                child: const Text('Continuar'),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _ChannelTile extends StatelessWidget {
  const _ChannelTile({
    required this.label,
    required this.isConnected,
    required this.isSelected,
    required this.onChanged,
  });

  final String label;
  final bool isConnected;
  final bool isSelected;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return CheckboxListTile(
      title: Text(label),
      subtitle: isConnected
          ? null
          : const Text('Não conectado — conecte nas Configurações.'),
      value: isSelected,
      onChanged: isConnected ? (v) => onChanged(v ?? false) : null,
    );
  }
}
