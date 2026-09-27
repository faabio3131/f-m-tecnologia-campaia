"""Request-level dependencies: real session auth, dev bearer fixture, step-up,
idempotency key extraction.

Invariant #1 from the spec: tenant_id is NEVER accepted from the client. It is derived
here, from the authenticated principal only, and nowhere else in the app reads a
client-supplied tenant_id.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from starlette.requests import Request

from campaia_core.identity_provider import IdentityError
from campaia_core.permissions import Principal

from .errors import ApiError
from .session import CSRF_HEADER_NAME, SESSION_COOKIE_NAME, SessionRecord
from .state import DEV_AUTH_FIXTURE_ALLOWED_ENVS, AppState, TokenPrincipal

MIN_IDEMPOTENCY_KEY_LEN = 16
MAX_IDEMPOTENCY_KEY_LEN = 128

#: SECURITY FIX (Fase 3, achado 2, 27/09/2026 -- auditoria independente): janela de
#: frescor exigida do PROPRIO instante de autenticacao do token (`VerifiedIdentity.
#: auth_time`) para que ele sirva de prova de step-up -- distinta de
#: `campaia_core.permissions.STEP_UP_MAX_AGE` (que rege por quanto tempo um step-up JA
#: CONCEDIDO continua valendo dentro do CampaIA). Um token com `auth_time` antigo pode
#: continuar criptograficamente valido (o provedor renova sessao em segundo plano) sem
#: que o usuario tenha se reautenticado de verdade recentemente -- por isso as duas
#: janelas sao propositalmente separadas e nunca a mesma constante.
STEP_UP_TOKEN_MAX_AUTH_AGE = timedelta(minutes=5)

#: Metodos que mutam estado -- exigem CSRF valido quando autenticados via sessao real
#: (cookie). O fixture de bearer token (dev/teste) nunca passa por aqui: nao usa cookie,
#: entao nao ha CSRF a verificar nesse caminho (mesma logica de qualquer API sem cookie).
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def get_state(request: Request) -> AppState:
    return request.app.state.campaia


def _require_session_record(request: Request, state: AppState) -> SessionRecord | None:
    """Caminho real (ADR-0018): sessao server-side via cookie HttpOnly. Devolve None se
    nao houver cookie (deixa require_auth tentar o fixture de dev/teste); levanta
    ApiError fail-closed se o cookie EXISTIR mas for invalido/expirado -- um cookie
    presente e ruim nunca cai silenciosamente para outro mecanismo. Devolve o
    `SessionRecord` inteiro (nao so o principal) para que WP-03 (memberships/switch,
    api/routes_auth.py) tenha acesso a `available_principals` sem uma segunda leitura da
    sessao."""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id is None:
        return None

    record = state.sessions.get(session_id)
    now = datetime.now(timezone.utc)
    if record is None or record.is_expired(now=now):
        raise ApiError("UNAUTHENTICATED", "Sessao invalida ou expirada.")

    if request.method in _MUTATING_METHODS:
        presented = request.headers.get(CSRF_HEADER_NAME)
        if not record.csrf_token_valid(presented):
            raise ApiError("PERMISSION_DENIED", "Token CSRF ausente ou invalido.")

    return record


def require_session_record(request: Request) -> SessionRecord:
    """Como `require_auth`, mas para os endpoints de WP-03 (`GET /me/memberships`,
    `POST /auth/session/switch`) que precisam do `SessionRecord` inteiro, nao so do
    principal ativo -- essas rotas so fazem sentido para sessao real (cookie); o fixture
    de bearer token de dev/teste nao tem conceito de "vinculos", entao e recusado aqui
    fail-closed em vez de fingir um `SessionRecord` sintetico."""
    state = get_state(request)
    record = _require_session_record(request, state)
    if record is None:
        raise ApiError(
            "UNAUTHENTICATED",
            "Esta operacao exige uma sessao real (cookie); o fixture de bearer token de "
            "teste nao tem vinculos multiplos.",
        )
    return record


def _require_auth_via_dev_fixture(request: Request, state: AppState) -> TokenPrincipal:
    """Fixture de bearer token, SOMENTE para test/dev-local (AppState garante, por
    construcao, que `state.tokens` fica vazio fora desses ambientes -- ver
    api/state.py::DEV_AUTH_FIXTURE_ALLOWED_ENVS). Nunca um formato de credencial real."""
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        raise ApiError("UNAUTHENTICATED", "Missing or malformed Authorization header.")
    token = header[len("Bearer ") :].strip()
    if not token:
        raise ApiError("UNAUTHENTICATED", "Empty bearer token.")

    principal = state.tokens.get(token)
    if principal is None:
        raise ApiError("UNAUTHENTICATED", "Unknown or expired token.")
    return principal


def require_auth(request: Request) -> TokenPrincipal:
    """Sessao real (cookie) primeiro; fixture de bearer token (test/dev-local) só como
    fallback quando nao ha cookie de sessao nenhum. 401/403 fail-closed em qualquer outro
    caso -- nunca um bypass silencioso entre os dois mecanismos."""
    state = get_state(request)

    record = _require_session_record(request, state)
    if record is not None:
        return record.principal

    return _require_auth_via_dev_fixture(request, state)


def session_key_for(request: Request) -> str:
    """Identificador da sessao/credencial corrente, para amarrar o step-up a ELA (Fase
    C3, 27/09/2026 -- auditoria independente) em vez de so `(tenant_id, user_id)`.

    Achado real: chaveado so por (tenant_id, user_id), um step-up sobrevivia
    indevidamente a logout->login (sessao nova, mesmo usuario) e a troca de
    tenant/unidade dentro da MESMA sessao -- nada nesse par muda nesses casos. Sessao
    real (cookie) usa o `session_id` do cookie; o fixture de bearer token (dev/teste,
    sem conceito de sessao) usa o proprio token como substituto -- muda a cada
    login/token diferente, mesma propriedade de nao sobreviver a uma nova "sessao".

    Publica (Fase 3, achado 3, 27/09/2026): tambem usada por
    `api/routes_auth.py::switch_membership` para invalidar TODO step-up da sessao no
    momento da troca -- nao so um detalhe interno deste modulo.
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id is not None:
        return f"session:{session_id}"
    header = request.headers.get("authorization", "")
    if header.startswith("Bearer "):
        return f"bearer:{header[len('Bearer '):].strip()}"
    return "no-session"


def note_step_up_header(request: Request, fixture: TokenPrincipal) -> None:
    """If X-Step-Up-Token is present and represents a genuine step-up, record "stepped
    up now" into AppState, keyed by (tenant_id, user_id, session_key) -- ver
    `session_key_for` (Fase C3) e `_is_genuine_step_up` (Fase C2/achados 1-2).

    Must run BEFORE any campaia_core.permissions.authorize() call on this request, since
    authorize() reads Principal.step_up_at to decide STEP_UP_REQUIRED itself (see
    permissions.py REQUIRES_STEP_UP / STEP_UP_MAX_AGE). If this ran after authorize(), the
    very first request with a valid header would still be rejected because the domain
    check would see step_up_at=None. This function never rejects -- it only records.
    """
    state = get_state(request)
    if _is_genuine_step_up(request, state, fixture):
        session_key = session_key_for(request)
        state.record_step_up(
            fixture.tenant_id, fixture.user_id, session_key, at=datetime.now(timezone.utc)
        )


def _is_genuine_step_up(request: Request, state: AppState, fixture: TokenPrincipal) -> bool:
    """SECURITY FIX (Fase C2, 27/09/2026; endurecido pelos achados 1 e 2 da auditoria
    independente #3, mesma data): a versao original aceitava QUALQUER valor nao-vazio de
    `X-Step-Up-Token` como reautenticacao valida, em qualquer ambiente -- isso nunca foi
    uma verificacao real, so uma conveniencia de sandbox documentada como tal. A correcao
    de Fase C2 exigiu um ID token real fora de test/dev-local, mas isso sozinho ainda
    nao bastava:

    - achado 1: validar que o token e' um ID token real, verificado, NAO prova que ele
      pertence ao mesmo usuario da sessao corrente -- um token real de OUTRO usuario
      elevaria a sessao de qualquer um. Corrigido comparando `identity.email` contra
      `fixture.email` (o e-mail do vinculo ATIVO desta sessao/token, resolvido pelo
      diretorio interno -- ver `api/identity_directory.py` e `api/state.py::
      TokenPrincipal.email`).
    - achado 2: um ID token pode continuar criptograficamente valido muito depois do
      login original (o provedor pode renovar a sessao em segundo plano) -- validade do
      token NAO prova reautenticacao recente. Corrigido exigindo `identity.auth_time`
      (instante real da autenticacao, nunca `iat`/expiracao do token/hora da requisicao)
      dentro de `STEP_UP_TOKEN_MAX_AUTH_AGE`.

    A conveniencia de "qualquer valor nao-vazio" continua existindo, mas SOMENTE em
    test/dev-local (mesmo guard de `DEV_AUTH_FIXTURE_ALLOWED_ENVS` usado para o fixture
    de bearer token) -- nao passa por nenhuma das checagens acima, por construcao (nao ha
    ID token real nenhum para verificar ou correlacionar nesse caminho). Em qualquer
    outro ambiente, o header tem que ser um ID token real, verificado pelo
    `state.id_token_verifier` ja usado para login (WP-02), pertencente ao MESMO e-mail
    do vinculo ativo, e recem-emitido -- hoje o verificador default e'
    `AlwaysRejectIdTokenVerifier` (nenhum projeto Firebase real configurado), entao o
    resultado pratico e' fail-closed em produção ate' um verificador real existir.
    """
    value = request.headers.get("x-step-up-token", "").strip()
    if not value:
        return False
    if state.env in DEV_AUTH_FIXTURE_ALLOWED_ENVS:
        return True
    try:
        identity = state.id_token_verifier.verify(value)
    except IdentityError:
        return False
    if identity.email != fixture.email:
        return False
    if (datetime.now(timezone.utc) - identity.auth_time) > STEP_UP_TOKEN_MAX_AUTH_AGE:
        return False
    return True


def require_step_up(request: Request, fixture: TokenPrincipal) -> None:
    """Back-compat explicit check, for permissions that are gated at the HTTP layer only
    (not every sensitive endpoint's permission is in campaia_core.permissions.
    REQUIRES_STEP_UP -- e.g. OAuth start has no dedicated Permission of its own beyond
    CONNECTION_MANAGE, which IS covered, so this mostly acts as a defence-in-depth
    re-check). Must be called AFTER note_step_up_header/authorize.

    Reusa `_is_genuine_step_up` (Fase C2/achados 1-2) -- mesmo criterio real/fixture do
    resto do fluxo de step-up, nunca "qualquer valor nao-vazio" fora de test/dev-local.
    """
    state = get_state(request)
    if not _is_genuine_step_up(request, state, fixture):
        raise ApiError(
            "STEP_UP_REQUIRED",
            "This operation requires a recent step-up re-authentication "
            "(X-Step-Up-Token header).",
        )


def require_idempotency_key(request: Request) -> str:
    key = request.headers.get("idempotency-key", "").strip()
    if not key:
        raise ApiError(
            "VALIDATION_FAILED",
            "This operation requires an Idempotency-Key header.",
            details={"header": "Idempotency-Key"},
        )
    if not (MIN_IDEMPOTENCY_KEY_LEN <= len(key) <= MAX_IDEMPOTENCY_KEY_LEN):
        raise ApiError(
            "VALIDATION_FAILED",
            f"Idempotency-Key must be {MIN_IDEMPOTENCY_KEY_LEN}-"
            f"{MAX_IDEMPOTENCY_KEY_LEN} characters.",
            details={"header": "Idempotency-Key", "length": len(key)},
        )
    return key


def build_domain_principal(
    request: Request, state: AppState, fixture: TokenPrincipal
) -> Principal:
    """Build the real campaia_core.permissions.Principal, including step_up_at.

    This makes the RBAC/ABAC checks in permissions.authorize (MFA, step-up recency,
    value ceilings) genuinely load-bearing rather than re-implemented at the HTTP layer.

    `request` (Fase C3, 27/09/2026): o step-up e' lido pela MESMA chave de sessao com
    que foi gravado (`session_key_for`) -- nunca so por (tenant_id, user_id), que
    sobreviveria indevidamente a um logout->login ou troca de tenant na mesma sessao.
    """
    session_key = session_key_for(request)
    step_up_at = state.last_step_up(fixture.tenant_id, fixture.user_id, session_key)
    return fixture.to_domain_principal(step_up_at=step_up_at)


def reject_client_tenant_id(body: dict) -> None:
    """Defence in depth: if a client-supplied body somehow carries tenant_id, refuse it
    rather than silently ignoring it. Pydantic-free version: `models.py` schemas simply
    do not declare a tenant_id field at all, so this only fires for raw/extra dict usage.
    """
    if "tenant_id" in body:
        raise ApiError(
            "VALIDATION_FAILED",
            "tenant_id is derived from the authenticated principal and must not be "
            "supplied by the client.",
            details={"field": "tenant_id"},
        )
