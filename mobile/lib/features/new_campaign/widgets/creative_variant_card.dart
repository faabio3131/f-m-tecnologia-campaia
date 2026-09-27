/// Cartao de uma variacao de criativo (secao 6.3): titulo, descricao, CTA e
/// formatos de imagem ja gerados. Puramente de exibicao nesta fatia -- a
/// edicao inline dos textos e o botao "Gerar outra versao" por formato
/// (secao 6.3) sao interacoes reais que dependem da integracao com o AI
/// Gateway, ainda inexistente aqui; os callbacks ficam como TODO explicito
/// em vez de simulados.
library;

import 'package:flutter/material.dart';

import '../state/new_campaign_state.dart';

class CreativeVariantCard extends StatelessWidget {
  const CreativeVariantCard({super.key, required this.variant});

  final CreativeVariant variant;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              variant.headline.isEmpty ? '(sem título ainda)' : variant.headline,
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 4),
            Text(
              variant.description.isEmpty
                  ? '(sem descrição ainda)'
                  : variant.description,
            ),
            const SizedBox(height: 4),
            Text(
              'CTA: ${variant.callToAction.isEmpty ? '(não definido)' : variant.callToAction}',
              style: const TextStyle(fontStyle: FontStyle.italic),
            ),
            if (variant.imageFormats.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                children: [
                  for (final format in variant.imageFormats)
                    Chip(label: Text(format)),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
