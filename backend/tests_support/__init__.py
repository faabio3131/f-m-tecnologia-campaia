"""Harness EXCLUSIVAMENTE de teste/E2E (Etapa 2, WP-02 Web).

NUNCA importado por `api/` ou `campaia_core/` (codigo de produto) -- garantido por
`backend/tests/test_architecture_boundaries.py` (teste arquitetural, roda na suite
normal). Nada aqui deve ser referenciado fora de `tests_support/`, `tests/`, `tests_api/`
ou scripts de E2E explicitos.

Nao adiciona nenhum endpoint de bypass -- so injeta um `IdTokenVerifier` deterministico
(`DeterministicTestIdTokenVerifier`) no `AppState` real, via os mesmos parametros de
construcao que qualquer chamador legitimo (`env`, `allowed_origins`, `id_token_verifier`)
ja usa. O protocolo de sessao/CSRF/cookie exercitado pelo E2E e o codigo real de
producao, nao uma simulacao.
"""
