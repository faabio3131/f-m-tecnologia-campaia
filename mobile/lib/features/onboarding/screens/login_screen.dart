/// Tela 3.1 (secao 3.1 da especificacao): Criar Conta / Login.
///
/// Campos: e-mail, senha (ou OAuth social, se decidido em bloco de
/// autenticacao separado -- nao coberto aqui). Sem armazenamento de senha em
/// texto puro (NON_FUNCTIONAL_REQUIREMENTS.md, secao 4.1) -- esta tela nunca
/// guarda a senha no [OnboardingState] nem em nenhum outro lugar; ela existe
/// apenas dentro do TextEditingController local, descartado no dispose().
library;

import 'package:flutter/material.dart';

import '../state/onboarding_state.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.state});

  final OnboardingState state;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  @override
  void dispose() {
    _emailController.dispose();
    // Senha nunca sai deste controller para o OnboardingState -- descartada
    // aqui, nao persistida em nenhuma camada de estado do app.
    _passwordController.dispose();
    super.dispose();
  }

  String? _validateEmail(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Informe seu e-mail.';
    }
    if (!value.contains('@') || !value.contains('.')) {
      return 'E-mail inválido.';
    }
    return null;
  }

  String? _validatePassword(String? value) {
    if (value == null || value.isEmpty) {
      return 'Informe sua senha.';
    }
    return null;
  }

  void _continue() {
    if (_formKey.currentState?.validate() ?? false) {
      // TODO(F1): integrar com o endpoint real de autenticacao quando a
      // camada de servico/repositorio for construida. Esta fatia cobre
      // apenas a estrutura de navegacao, nao a chamada de rede.
      widget.state.goToNextStep();
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
              'Crie sua conta ou entre',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 24),
            TextFormField(
              controller: _emailController,
              keyboardType: TextInputType.emailAddress,
              autofillHints: const [AutofillHints.email],
              decoration: const InputDecoration(labelText: 'E-mail'),
              validator: _validateEmail,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _passwordController,
              obscureText: true,
              autofillHints: const [AutofillHints.password],
              decoration: const InputDecoration(labelText: 'Senha'),
              validator: _validatePassword,
            ),
            const SizedBox(height: 32),
            FilledButton(
              onPressed: _continue,
              child: const Text('Continuar'),
            ),
          ],
        ),
      ),
    );
  }
}
