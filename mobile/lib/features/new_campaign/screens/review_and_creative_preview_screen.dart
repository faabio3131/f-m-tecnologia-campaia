/// Tela 3 do fluxo de Nova Campanha: Revisão e Prévia do Criativo.
///
/// Consolida a Etapa 3 - Criativos (secao 6.3), Etapa 4 - Prévia por Canal
/// (secao 6.4) e o resumo final da Etapa 5 - Aprovação (secao 6.5),
/// enquanto o pedido desta fatia foi "Revisão e Pré-visualização do
/// Criativo gerado" -- as 3 acoes completas de aprovador (Aprovar/
/// Rejeitar/Solicitar Ajustes, secao 6.5) sao de um fluxo de aprovacao
/// separado, verificado por permissao (F10.3), que esta tela nao
/// implementa: aqui o CRIADOR da campanha revisa e ENVIA para aprovacao
/// (botao "Enviar para Aprovação"), reforçando visualmente a regra
/// inegociavel de que nenhuma campanha e' publicada sem essa etapa
/// separada (secao 6.5: "nenhuma publicação acontece sem essa etapa" —
/// selo "Nenhuma campanha é publicada sem sua aprovação").
library;

import 'package:flutter/material.dart';

import '../state/new_campaign_state.dart';
import '../widgets/creative_variant_card.dart';

class ReviewAndCreativePreviewScreen extends StatelessWidget {
  const ReviewAndCreativePreviewScreen({
    super.key,
    required this.state,
    this.onSubmitForApproval,
  });

  final NewCampaignState state;
  final VoidCallback? onSubmitForApproval;

  static const Map<CampaignChannel, String> _channelLabels = {
    CampaignChannel.googleAds: 'Google Ads',
    CampaignChannel.meta: 'Meta (Facebook/Instagram)',
    CampaignChannel.whatsAppBusiness: 'WhatsApp Business',
  };

  static const Map<CampaignObjective, String> _objectiveLabels = {
    CampaignObjective.leads: 'Leads',
    CampaignObjective.sales: 'Vendas',
    CampaignObjective.visits: 'Visitas',
    CampaignObjective.messages: 'Mensagens',
  };

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: state,
      builder: (context, _) {
        final briefing = state.briefing;
        final bool canSubmit = state.allCreativesPassedPolicyCheck;

        return Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Revise antes de enviar para aprovação',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              Expanded(
                child: ListView(
                  children: [
                    _SummarySection(
                      objective: briefing.objective != null
                          ? _objectiveLabels[briefing.objective]!
                          : '—',
                      budget: briefing.totalBudget,
                      autonomyMode: state.autonomyMode,
                    ),
                    const SizedBox(height: 16),
                    for (final channel in briefing.selectedChannels)
                      _ChannelCreativeSection(
                        title: _channelLabels[channel]!,
                        creative: state.creativeFor(channel),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              const _AlwaysManualApprovalBanner(),
              const SizedBox(height: 16),
              Row(
                children: [
                  TextButton(
                    onPressed: state.goToPreviousStep,
                    child: const Text('Voltar'),
                  ),
                  const Spacer(),
                  FilledButton(
                    onPressed: canSubmit ? onSubmitForApproval : null,
                    child: const Text('Enviar para Aprovação'),
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

class _SummarySection extends StatelessWidget {
  const _SummarySection({
    required this.objective,
    required this.budget,
    required this.autonomyMode,
  });

  final String objective;
  final double? budget;
  final AutonomyMode autonomyMode;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Resumo da campanha',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text('Objetivo: $objective'),
            Text(
              'Orçamento total: '
              '${budget != null ? 'R\$ ${budget!.toStringAsFixed(2)}' : '—'}',
            ),
            Text(
              'Modo de autonomia da conta: '
              '${autonomyMode == AutonomyMode.manual ? 'Manual (Nível 1)' : 'Automático (Nível 2)'}',
            ),
          ],
        ),
      ),
    );
  }
}

class _ChannelCreativeSection extends StatelessWidget {
  const _ChannelCreativeSection({required this.title, required this.creative});

  final String title;
  final ChannelCreative? creative;

  @override
  Widget build(BuildContext context) {
    final status = creative?.policyStatus ?? PolicyCheckStatus.pending;
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(width: 8),
              _PolicyBadge(status: status, note: creative?.policyNote),
            ],
          ),
          const SizedBox(height: 8),
          if (creative == null || creative!.variants.isEmpty)
            const Text('Criativo ainda não gerado para este canal.')
          else
            for (final variant in creative!.variants)
              CreativeVariantCard(variant: variant),
        ],
      ),
    );
  }
}

class _PolicyBadge extends StatelessWidget {
  const _PolicyBadge({required this.status, this.note});

  final PolicyCheckStatus status;
  final String? note;

  @override
  Widget build(BuildContext context) {
    switch (status) {
      case PolicyCheckStatus.approved:
        return const Chip(label: Text('Aprovado pela política'));
      case PolicyCheckStatus.needsReview:
        return Chip(label: Text('Revisar: ${note ?? 'motivo não informado'}'));
      case PolicyCheckStatus.pending:
        return const Chip(label: Text('Verificação pendente'));
    }
  }
}

/// Mesmo selo mencionado na secao 6.5 ("Nenhuma campanha é publicada sem
/// sua aprovação") -- repetido aqui, na ultima tela antes do envio, para
/// que a mensagem chegue ao usuario no momento exato da decisao.
class _AlwaysManualApprovalBanner extends StatelessWidget {
  const _AlwaysManualApprovalBanner();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: Theme.of(context).colorScheme.outline),
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Row(
        children: [
          Icon(Icons.verified_user_outlined),
          SizedBox(width: 8),
          Expanded(
            child: Text('Nenhuma campanha é publicada sem sua aprovação.'),
          ),
        ],
      ),
    );
  }
}
