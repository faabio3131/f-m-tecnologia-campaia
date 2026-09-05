/// Tela 3.2 (secao 3.2 da especificacao): Cadastro da Empresa (F1.1).
///
/// Campos obrigatorios: nome da empresa, CNPJ, tipo de negocio (select
/// generico -- NAO e' uma lista de vertical especifico como "restaurante";
/// isso e' a decisao D-03: "qualquer pequeno negocio local"), idioma.
/// Validacao: CNPJ formatado; unicidade de nome por tenant fica a cargo do
/// backend (nao verificavel no cliente).
library;

import 'package:flutter/material.dart';

import '../state/onboarding_state.dart';

class CompanyRegistrationScreen extends StatefulWidget {
  const CompanyRegistrationScreen({super.key, required this.state});

  final OnboardingState state;

  @override
  State<CompanyRegistrationScreen> createState() =>
      _CompanyRegistrationScreenState();
}

class _CompanyRegistrationScreenState
    extends State<CompanyRegistrationScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _nameController;
  late final TextEditingController _cnpjController;
  BusinessType? _businessType;

  // CNPJ no formato 00.000.000/0000-00 -- apenas checagem de formato,
  // nao de digito verificador (validacao completa de CNPJ e' regra de
  // dominio, nao de UI, e fica no backend).
  static final RegExp _cnpjFormat =
      RegExp(r'^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$');

  static const Map<BusinessType, String> _businessTypeLabels = {
    BusinessType.ecommerce: 'E-commerce',
    BusinessType.services: 'Serviços',
    BusinessType.saas: 'SaaS',
    BusinessType.realEstate: 'Imobiliário',
    BusinessType.physicalRetail: 'Varejo físico',
    BusinessType.other: 'Outro',
  };

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.state.companyName);
    _cnpjController = TextEditingController(text: widget.state.cnpj);
    _businessType = widget.state.businessType;
  }

  @override
  void dispose() {
    _nameController.dispose();
    _cnpjController.dispose();
    super.dispose();
  }

  String? _validateName(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Informe o nome da empresa.';
    }
    return null;
  }

  String? _validateCnpj(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Informe o CNPJ.';
    }
    if (!_cnpjFormat.hasMatch(value.trim())) {
      return 'Use o formato 00.000.000/0000-00.';
    }
    return null;
  }

  void _continue() {
    if (_businessType == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Selecione o tipo de negócio.')),
      );
      return;
    }
    if (_formKey.currentState?.validate() ?? false) {
      widget.state
        ..companyName = _nameController.text.trim()
        ..cnpj = _cnpjController.text.trim()
        ..businessType = _businessType
        ..goToNextStep();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Form(
        key: _formKey,
        child: ListView(
          children: [
            const Text(
              'Sobre sua empresa',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 24),
            TextFormField(
              controller: _nameController,
              decoration: const InputDecoration(labelText: 'Nome da empresa'),
              validator: _validateName,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _cnpjController,
              decoration: const InputDecoration(
                labelText: 'CNPJ',
                hintText: '00.000.000/0000-00',
              ),
              validator: _validateCnpj,
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<BusinessType>(
              // `value` (nao `initialValue`) por compatibilidade com o piso
              // de versao declarado em pubspec.yaml (Flutter >=3.22.0) --
              // `initialValue` so existe a partir do Flutter 3.32.
              value: _businessType,
              decoration: const InputDecoration(labelText: 'Tipo de negócio'),
              items: [
                for (final entry in _businessTypeLabels.entries)
                  DropdownMenuItem(
                    value: entry.key,
                    child: Text(entry.value),
                  ),
              ],
              onChanged: (value) => setState(() => _businessType = value),
            ),
            const SizedBox(height: 32),
            Row(
              children: [
                TextButton(
                  onPressed: widget.state.goToPreviousStep,
                  child: const Text('Voltar'),
                ),
                const Spacer(),
                FilledButton(
                  onPressed: _continue,
                  child: const Text('Continuar'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
