/// Dialogo de confirmacao por senha de administrador (secao 9.1.1, Passo
/// 3), acionado ao tentar mudar de Manual para Automatico.
///
/// A senha digitada NUNCA sai deste widget para o NewCampaignState -- ela e'
/// mantida apenas no TextEditingController local, descartada no dispose(),
/// e o widget so devolve o resultado da tentativa de confirmacao (via
/// Navigator.pop) para quem o abriu. Isso segue a mesma disciplina do
/// LoginScreen do onboarding (senha nunca persistida em texto puro em
/// nenhuma camada de estado do app).
///
/// A VALIDACAO REAL da senha (chamada ao backend) nao existe nesta fatia --
/// [onValidatePassword] e' injetado por quem abre o dialogo, e esta tela
/// nao assume nenhum resultado sem essa chamada explicita.
library;

import 'package:flutter/material.dart';

/// Assinatura da funcao que valida a senha do administrador contra o
/// backend. Retorna `true` se a senha estiver correta. Nesta fatia, quem
/// constrói o dialogo deve fornecer uma implementacao real (ainda nao
/// existente) -- nao ha um default que finge validar.
typedef PasswordValidator = Future<bool> Function(String password);

class AutomaticModePasswordDialog extends StatefulWidget {
  const AutomaticModePasswordDialog({
    super.key,
    required this.onValidatePassword,
  });

  final PasswordValidator onValidatePassword;

  @override
  State<AutomaticModePasswordDialog> createState() =>
      _AutomaticModePasswordDialogState();
}

class _AutomaticModePasswordDialogState
    extends State<AutomaticModePasswordDialog> {
  final _passwordController = TextEditingController();
  bool _isValidating = false;
  bool _showInvalidPasswordError = false;

  @override
  void initState() {
    super.initState();
    // Sem isto, o botao "Confirmar e Ativar" so reavaliaria
    // _passwordController.text.isEmpty no proximo rebuild disparado por
    // outro motivo -- o campo de senha por si so nao aciona setState.
    _passwordController.addListener(_onPasswordChanged);
  }

  void _onPasswordChanged() => setState(() {});

  @override
  void dispose() {
    _passwordController.removeListener(_onPasswordChanged);
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _confirm() async {
    setState(() {
      _isValidating = true;
      _showInvalidPasswordError = false;
    });

    final bool isValid =
        await widget.onValidatePassword(_passwordController.text);

    if (!mounted) return;

    if (isValid) {
      Navigator.of(context).pop(true);
    } else {
      // Mensagem generica de erro (secao 9.1.1: "nao revela se o
      // e-mail/usuario existe"). Limite de tentativas antes de bloqueio
      // temporario e' responsabilidade do backend, nao desta tela.
      setState(() {
        _isValidating = false;
        _showInvalidPasswordError = true;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Confirmar ativação do Modo Automático'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Ao confirmar, você autoriza o CampaIA a otimizar '
            'automaticamente, dentro dos limites definidos, campanhas já '
            'aprovadas por você. Este evento fica registrado com data, '
            'hora e usuário para sua segurança.',
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _passwordController,
            obscureText: true,
            autofocus: true,
            decoration: InputDecoration(
              labelText: 'Senha do administrador',
              errorText: _showInvalidPasswordErrorText,
            ),
            onSubmitted: (_) => _confirm(),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Cancelar'),
        ),
        FilledButton(
          onPressed: (_isValidating || _passwordController.text.isEmpty)
              ? null
              : _confirm,
          child: const Text('Confirmar e Ativar'),
        ),
      ],
    );
  }

  String? get _showInvalidPasswordErrorText =>
      _showInvalidPasswordError ? 'Senha incorreta.' : null;
}
