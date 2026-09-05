# FONTE PRIMÁRIA — DECISÃO ADR-0012: ESTRATÉGIA DE AUTENTICAÇÃO DE USUÁRIOS

**Capturado em:** 27 de agosto de 2026
**Capturado por:** Claude, a partir de texto literal recebido do Diretor no turno corrente
**Diretor:** Fábio Aluizio da Silva

---

## SEQUÊNCIA DOS FATOS

1. Com D-08/ADR-0009 já aprovadas (Google Cloud, região São Paulo), restava decidir a estratégia de autenticação de usuários do CAMPAIA — item que não correspondia a nenhuma decisão D-numerada prévia do Diretor, apenas a uma recomendação técnica nova a ser apresentada.
2. Diretor pediu para entender melhor as alternativas antes de decidir ("Quero entender melhor as alternativas.").
3. Claude apresentou três opções com vantagens, custos, riscos e reversibilidade de cada uma:
   - **Opção A — Autenticação própria (construída do zero):** controle total, mas risco de segurança elevado (hash de senha, fluxos de recuperação) para uma equipe pequena, e baixa reversibilidade após usuários reais existirem.
   - **Opção B — Google Identity Platform (recomendação técnica):** serviço gerenciado nativo do GCP (já escolhido em D-08), cobre login e-mail/senha, login social, redefinição de senha, suporte nativo a multi-tenant; reduz superfície de risco de segurança; mesmo ecossistema/faturamento já adotado.
   - **Opção C — Terceiro especializado (ex.: Auth0, Clerk, Okta):** recursos avançados, mas fornecedor adicional fora do GCP, contrariando a lógica de unificação de provedor que motivou D-08/ADR-0009.
4. Claude recomendou explicitamente a Opção B, por ser a que menos gera trabalho extra e menos risco de segurança para uma equipe pequena, aproveitando a escolha de nuvem já feita.
5. Diretor confirmou a recomendação técnica.

## RESPOSTA LITERAL DO DIRETOR

> "Opção B — Google Identity Platform (minha recomendação) vamos usar essa"

## DECISÃO

**ADR-0012 = Google Identity Platform** é o serviço de autenticação de usuários do CAMPAIA — cobrindo login por e-mail/senha e login social, com suporte a separação lógica multi-tenant entre os usuários de cada cliente contratante.

**Esta decisão não resolve:** o desenho detalhado de como o backend (`campaia_core`) valida os tokens emitidos pelo Identity Platform em cada requisição, nem o fluxo de convite/provisionamento de usuários por tenant — trabalho de engenharia futuro, dependente da Fase 2 (infraestrutura real), com D-08 e ADR-0012 já aprovadas.
