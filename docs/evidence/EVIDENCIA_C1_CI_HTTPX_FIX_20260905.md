# CAMPAIA — Evidência: Correção do erro real de CI (dependência `httpx` ausente)

**Data:** 05/09/2026
**Bloco:** C1 (repositório Git + CI), pós-publicação no GitHub
**Gatilho:** Diretor reportou "vc viu que tem um ero de CI dependência e revalidação" após verificar a aba
Actions do repositório `https://github.com/faabio3131/CampaIA` e ver um ✗ vermelho no último commit.

---

## 1. Contexto

O painel v16 registrava o C1 (repositório Git + CI) como "construído e entregue", mas com uma pendência
explícita: faltava a decisão do Diretor sobre qual host Git remoto usar, sem o qual o GitHub Actions não
rodaria de fato (workflow escrito, mas nunca executado em ambiente real).

Nesta sessão, o Diretor:
1. Criou o repositório `https://github.com/faabio3131/CampaIA` (privado).
2. Conectou o repositório e recebeu o push do repositório completo (confirmado em sessão anterior).
3. Instalou o GitHub CLI (`gh`) na própria máquina e autenticou via `gh auth login` (login por navegador,
   device code flow) — nenhuma senha, token ou credencial passou por mim em nenhum momento.
4. Abriu a aba Actions do repositório e reportou um erro real de CI.

## 2. Diagnóstico

Em vez de navegar visualmente pelo site do GitHub (onde meu acesso de tela é apenas leitura), usei o `gh`
já autenticado, diretamente no terminal do Diretor (Git CMD, acesso "full" concedido pelo próprio Diretor):

```
gh run view 33940688330 --log-failed > %USERPROFILE%\Desktop\ci_error_log.txt
```

O arquivo de log (97959 bytes) foi transferido para leitura completa. Buscando por padrões de erro
(`ModuleNotFoundError`, `Traceback`, `FAILED`), a causa real ficou clara:

```
ERROR: tests_api.test_helpers (unittest.loader._FailedTest.tests_api.test_helpers)
ImportError: Failed to import test module: tests_api.test_helpers
Traceback (most recent call last):
  ...
ModuleNotFoundError: No module named 'httpx'
During handling of the above exception, another exception occurred:
  ...
RuntimeError: The starlette.testclient module requires the httpx package to be installed.
```

O mesmo padrão se repetiu para `tests_api.test_invariants`, `tests_api.test_persistence` e
`tests_api.test_smoke_endpoints` — 4 dos 5 arquivos de teste da camada de API falharam ao importar.
A suíte de domínio (263 testes) passou integralmente ("ok" em todos); o resultado final foi
`FAILED (errors=4)` e `Process completed with exit code 1`.

**Causa raiz:** `backend/requirements.txt` listava apenas `pydantic` e `starlette`. O `starlette.testclient`
— usado pelos testes da camada de API — depende do pacote `httpx`, que nunca foi declarado como
dependência. Na minha sandbox de desenvolvimento, os 343 testes sempre passaram porque o `httpx` já estava
instalado ali por outro motivo (não relacionado a este projeto), mascarando a dependência real ausente. O
ambiente limpo do GitHub Actions, que instala exatamente o que está em `requirements.txt` e nada mais,
expôs o problema real.

O aviso adicional presente no log ("Node.js 20 is deprecated... actions/checkout@v4 forced to run on
Node.js 24") é apenas um aviso de infraestrutura interna do GitHub Actions sobre a versão do Node.js usada
por baixo dos panos pelas próprias actions — não afeta Python nem os testes, e não foi a causa da falha.

## 3. Correção

1. Confirmada a versão estável mais recente do `httpx` publicada no PyPI antes de fixar qualquer número
   (mesma disciplina já aplicada a `pydantic==2.13.3` e `starlette==1.0.0`): **0.28.1**, publicada em
   06/12/2024, confirmado via `WebFetch` direto em `https://pypi.org/project/httpx/`.
2. `backend/requirements.txt` corrigido para:
   ```
   pydantic==2.13.3
   starlette==1.0.0
   httpx==0.28.1
   ```
3. Suíte completa re-executada na sandbox após a correção: 263 (domínio) + 80 (API) = **343/343
   aprovados**, zero regressão.
4. Tentativa de reprodução em ambiente Python limpo (`venv`) nesta sandbox: bloqueada pela mesma restrição
   de rede já documentada no projeto (P-13/P-18) — sem acesso a `pypi.org` para instalar pacotes num venv
   novo. A correção não depende dessa reprodução: a causa foi confirmada diretamente pelo log real do
   GitHub Actions (fonte primária), não por inferência.
5. Commit e push realizados diretamente no terminal do Diretor (clone real, sincronizado com
   `origin/main`), usando o `git`/`gh` já autenticados por ele:
   ```
   git add backend/requirements.txt
   git commit -m "Corrige dependencia ausente do CI: adiciona httpx a backend/requirements.txt"
   git push
   ```
   Resultado: `ab4173a..3f2c18d  main -> main`.

## 4. Verificação do resultado

O push disparou automaticamente uma nova execução do workflow. Confirmação objetiva, não presumida:

```
gh run view 33977148976 --json status,conclusion
{
  "conclusion": "success",
  "status": "completed"
}
```

Execução concluída em 14 segundos, com sucesso.

## 5. Sincronização com o Google Drive

O arquivo `backend/requirements.txt` antigo (fileId `12XdaSjTs09Cz2bhEDrqF2agY71f4Bo5L`) foi movido para a
lixeira e substituído por uma nova versão com o conteúdo corrigido (fileId `1GqmKoroeq7h-aS1OB9lDyijQtnmFzafq`).
Verificação byte a byte: download do conteúdo recém-enviado, decodificado e comparado por `diff` e SHA256
contra o arquivo local — resultado idêntico (`fe2f7eb46845476fa99f72ce269f73f92eae4bb8c4492683baa7869c844d8eff`
em ambos).

## 6. Estado final

- Repositório: `https://github.com/faabio3131/CampaIA` (privado).
- CI: **verde**, rodando de fato a cada push.
- Google Drive: `backend/requirements.txt` atualizado e verificado.
- Nenhuma outra dependência ou defeito adicional encontrado durante este diagnóstico.
