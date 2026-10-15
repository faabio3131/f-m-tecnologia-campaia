# WP-R01 — retomada da homologação externa G2

Data local: 14/10/2026 (America/Sao_Paulo).
Status: PARTIAL. Homologação externa: BLOCKED / EXTERNAL_INFRASTRUCTURE.

## CURRENT e escopo

- Repositório: faabio3131/f-m-tecnologia-campaia.
- Base inspecionada: main@4d17f41c35d95ff473ab420be5164407c9166bb5.
- Clone local na main, git status --short vazio antes da investigação.
- PR #43 aberta em Draft, HEAD 88a8922f359a7b19b23940168bf00107e747812f; AGENTS.md lido nessa versão, ainda ausente na main.
- Objetivo: homologar login/step-up, administração sensível, revogação, autoridade final e isolamento no staging.
- Fora de escopo: reconstruir IAM, alterar produção, credenciais, migrations, deploy e demais WPs.
- Nenhuma alteração funcional realizada; G0/G1/G3/G4 preservados como certificados historicamente, sem recertificação nesta execução.

## Fatos confirmados nesta execução

1. Workflows pós-merge da base: Backend #223 (38651090662), Frontend #161 (38651090660) e F4 Platform CI #57 (38651090675), todos completed/success, consultados pelo conector GitHub.
2. Testes focados locais:
   `python -m unittest tests_api.test_organization_admin tests_api.test_organization_persistence tests_api.test_step_up_security -q`
   executado em backend, com venv isolado e requirements.txt da base: 30 testes, OK.
   Há warning de depreciação Starlette/TestClient/httpx; nenhum teste falhou.
3. Staging Web: https://campaia-web-staging-dt4sxvfxra-rj.a.run.app.
   A raiz mostrou scaffold WP-01; no código da base, web/src/app/page.tsx redireciona para /login. Existe divergência observável entre a superfície servida e a base, sem prova da revisão/digest em execução.
4. /login ofereceu Google real. O usuário escolheu sua conta e confirmou a verificação no dispositivo. Depois, a página CampaIA exibiu “Não foi possível entrar” e “Erro HTTP 500”. Não foi observada sessão autenticada no produto.
5. GET público ao proxy /api/campaia/health/ready via curl com --max-time 30 não recebeu bytes e encerrou com exit 28 / HTTP 000. Timeout de uma sonda não prova indisponibilidade permanente nem causa raiz.
6. Desktop Commander list_devices reportou o único dispositivo cadastrado offline. Não foi executado comando no host remoto.
7. O console Cloud SQL solicitado no navegador retornou “Site Unavailable”; nenhum estado de infraestrutura foi obtido.
8. Não há gcloud disponível neste runtime; não houve consulta autenticada de logs ou revisão Cloud Run.

## Hipóteses e limites

- Cloud SQL desligado é hipótese: docs/runbooks/F4_STAGING_BOOTSTRAP_RUNBOOK_20261001.md, seção 8.1, prevê banco ligado somente durante testes; infra/scripts/staging-runtime.sh permite status/start/stop.
- Revisão Web antiga é hipótese compatível com o scaffold observado; falta consultar imagem, digest, revisão e tráfego reais.
- Não há causa raiz comprovada para o HTTP 500. Não houve correção ou workaround.
- Os 30 testes usam ambiente determinístico e não substituem Google/Cloud SQL reais.
- G2 não promovido a DONE_VERIFIED; step-up/mutações/revogação/isolamento externos ainda não executados.

## Continuação exata

1. Restabelecer canal autenticado de leitura da infraestrutura (por exemplo, Desktop Commander online).
2. Consultar, sem modificar: estado/activationPolicy do Cloud SQL; revisões, imagens e tráfego de ambos os serviços Cloud Run; logs sanitizados no intervalo do erro (aproximadamente 15/10/2026 01:20–01:26 UTC). Não exportar cookies, tokens, payloads de identidade ou dados pessoais.
3. Correlacionar logs com HTTP 500 antes de escolher correção.
4. Se necessário ligar o banco, atualizar staging, executar migrations ou alterar segredo, apresentar o alvo e obter autorização específica conforme o prompt mestre. O workflow de release existente inclui migration real e não deve ser acionado apenas para diagnóstico.
5. Retomar login e novo step-up e executar toda a matriz WP-R01, incluindo auditoria e sessão revogada.
6. Somente então atualizar o Controle Mestre e solicitar o próximo gate.

## Governança

Nenhum merge, deploy, migration, start/stop de infraestrutura, criação/rotação de segredo, alteração de acesso ou mutação de tenant foi executado. Esta evidência registra um bloqueio, não certifica o G2. Não exige rollback funcional porque não altera comportamento.
