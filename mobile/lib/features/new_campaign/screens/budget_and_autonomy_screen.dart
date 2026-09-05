/// Tela 2 do fluxo de Nova Campanha: Orçamento e Regra de Autonomia.
///
/// Cobre o orçamento total (parte da Etapa 1 - Briefing, secao 6.1) e a
/// escolha do modo de autonomia (secao 9.1/9.1.1) no contexto desta
/// campanha. A configuracao de autonomia e' tecnicamente uma configuracao
/// DA CONTA (nao desta campanha isolada) -- esta tela a expoe aqui porque
/// e' o ponto do fluxo onde o usuario decide como as futuras otimizacoes
/// desta campanha serao tratadas, mas o estado (NewCampaignState) e' claro
/// que a configuracao persiste alem desta campanha.
///
/// Aviso obrigatorio nesta tela, fiel a especificacao (secao 9.1, badge
/// "Requer senha de administrador para ativar"; secao 9.1.1, regra de
/// campanha nova): campanha NOVA sempre exige aprovacao manual, mesmo com
/// Modo Automatico ativo -- isso e' mostrado de forma visivel, nao apenas
/// como regra de backend invisivel (mesma filosofia da secao 6.5).
library;

import 'package:flutter/material.dart';

import '../state/new_campaign_state.dart';
import '../widgets/automatic_mode_password_dialog.dart';

class BudgetAndAutonomyScreen extends StatefulWidget {
  const BudgetAndAutonomyScreen({super.key, required this.state});

  final NewCampaignState state;

  @override
  State<BudgetAndAutonomyScreen> createState() =>
      _BudgetAndAutonomyScreenState();
}

class _BudgetAndAutonomyScreenState extends State<BudgetAndAutonomyScreen> {
  late final TextEditingController _budgetController;

  @override
  void initState() {
    super.initState();
    final currentBudget = widget.state.briefing.totalBudget;
    _budgetController = TextEditingController(
      text: currentBudget != null ? currentBudget.toStringAsFixed(2) : '',
    );
  }

  @override
  void dispose() {
    _budgetController.dispose();
    super.dispose();
  }

  void _onBudgetChanged(String value) {
    final normalized = value.replaceAll(',', '.');
    final parsed = double.tryParse(normalized);
    if (parsed != null) {
      widget.state.setTotalBudget(parsed);
    }
  }

  Future<void> _onSelectAutonomyMode(AutonomyMode mode) async {
    if (mode == AutonomyMode.manual) {
      widget.state.switchToManualMode();
      return;
    }

    // secao 9.1.1: a troca Manual -> Automatico exige o fluxo de senha, "nao
    // e' uma troca simples de toggle".
    final bool? activated = await showDialog<bool>(
      context: context,
      builder: (context) => AutomaticModePasswordDialog(
        // TODO(Fase 8+): substituir por chamada real ao endpoint de
        // reautenticacao do administrador. Nesta fatia nao ha integracao
        // de rede -- deliberado, mesma decisao do onboarding.
        onValidatePassword: (password) async => false,
      ),
    );

    if (activated == true) {
      widget.state.confirmAutomaticModeWithPassword(passwordIsValid: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.state,
      builder: (context, _) {
        final mode = widget.state.autonomyMode;
        return Padding(
          padding: const EdgeInsets.all(24),
          child: ListView(
            children: [
              const Text(
                'Qual é o orçamento desta campanha?',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _budgetController,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(
                  labelText: 'Orçamento total (R\$)',
                ),
                onChanged: _onBudgetChanged,
              ),
              const SizedBox(height: 32),
              const Text(
                'Como o CampaIA deve operar?',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),
              _AutonomyModeCard(
                title: 'Modo Manual (Nível 1)',
                description:
                    'Toda campanha passa por sua aprovação antes de '
                    'publicar.',
                isSelected: mode == AutonomyMode.manual,
                onTap: () => _onSelectAutonomyMode(AutonomyMode.manual),
              ),
              const SizedBox(height: 12),
              _AutonomyModeCard(
                title: 'Modo Automático (Nível 2)',
                description:
                    'Defina um limite e deixe o CampaIA otimizar suas '
                    'campanhas já aprovadas dentro dele, sem precisar '
                    'aprovar cada ajuste. Campanhas novas continuam sempre '
                    'passando por sua aprovação.',
                badge: 'Requer senha de administrador para ativar',
                isSelected: mode == AutonomyMode.automatic,
                onTap: () => _onSelectAutonomyMode(AutonomyMode.automatic),
              ),
              const SizedBox(height: 24),
              const _ManualApprovalNotice(),
              const SizedBox(height: 32),
              Row(
                children: [
                  TextButton(
                    onPressed: widget.state.goToPreviousStep,
                    child: const Text('Voltar'),
                  ),
                  const Spacer(),
                  FilledButton(
                    onPressed: widget.state.canProceedFromBudgetAndAutonomy
                        ? widget.state.goToNextStep
                        : null,
                    child: const Text('Continuar'),
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

class _AutonomyModeCard extends StatelessWidget {
  const _AutonomyModeCard({
    required this.title,
    required this.description,
    required this.isSelected,
    required this.onTap,
    this.badge,
  });

  final String title;
  final String description;
  final String? badge;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: isSelected
          ? Theme.of(context).colorScheme.primaryContainer
          : null,
      child: ListTile(
        onTap: onTap,
        leading: Icon(
          isSelected ? Icons.radio_button_checked : Icons.radio_button_off,
        ),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(description),
            if (badge != null) ...[
              const SizedBox(height: 4),
              Text(
                badge!,
                style: const TextStyle(fontStyle: FontStyle.italic),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Aviso fixo e sempre visivel (independente do modo escolhido) de que
/// campanha nova nunca pula a aprovacao humana -- secao 6.5 e
/// DECISOES_DIRETOR.md item 5 sao explicitos que isso deve ser visivelmente
/// claro para o usuario, nao apenas uma regra de backend invisivel.
class _ManualApprovalNotice extends StatelessWidget {
  const _ManualApprovalNotice();

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
            child: Text(
              'Nenhuma campanha nova é publicada sem sua aprovação, '
              'mesmo com o Modo Automático ativo.',
            ),
          ),
        ],
      ),
    );
  }
}
