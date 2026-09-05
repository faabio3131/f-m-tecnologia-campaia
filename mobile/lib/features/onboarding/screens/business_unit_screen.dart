/// Tela 3.3 (secao 3.3 da especificacao): Unidade de Negocio (F1.2).
///
/// Campos: nome da unidade (filial/marca/regiao), endereco (se aplicavel ao
/// tipo de negocio). Pode ser pulada com "Adicionar depois" -- uma empresa
/// pode operar com uma unica unidade padrao.
library;

import 'package:flutter/material.dart';

import '../state/onboarding_state.dart';

class BusinessUnitScreen extends StatefulWidget {
  const BusinessUnitScreen({super.key, required this.state});

  final OnboardingState state;

  @override
  State<BusinessUnitScreen> createState() => _BusinessUnitScreenState();
}

class _BusinessUnitScreenState extends State<BusinessUnitScreen> {
  late final TextEditingController _nameController;
  late final TextEditingController _addressController;

  @override
  void initState() {
    super.initState();
    _nameController =
        TextEditingController(text: widget.state.businessUnitName);
    _addressController =
        TextEditingController(text: widget.state.businessUnitAddress);
  }

  @override
  void dispose() {
    _nameController.dispose();
    _addressController.dispose();
    super.dispose();
  }

  void _continue() {
    widget.state
      ..businessUnitName = _nameController.text.trim()
      ..businessUnitAddress = _addressController.text.trim()
      ..businessUnitSkipped = false
      ..goToNextStep();
  }

  void _skip() => widget.state.skipBusinessUnit();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: ListView(
        children: [
          const Text(
            'Unidade de negócio',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          const Text(
            'Opcional agora — você pode adicionar depois nas configurações.',
          ),
          const SizedBox(height: 24),
          TextField(
            controller: _nameController,
            decoration: const InputDecoration(
              labelText: 'Nome da unidade (filial/marca/região)',
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _addressController,
            decoration: const InputDecoration(labelText: 'Endereço'),
          ),
          const SizedBox(height: 32),
          Row(
            children: [
              TextButton(
                onPressed: widget.state.goToPreviousStep,
                child: const Text('Voltar'),
              ),
              const Spacer(),
              TextButton(
                onPressed: _skip,
                child: const Text('Adicionar depois'),
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed: _continue,
                child: const Text('Continuar'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
