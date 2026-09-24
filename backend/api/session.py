"""Sessao server-side real (ADR-0018, item 1.3/WP-02).

Cookie `HttpOnly`/`Secure`/`SameSite=Lax` carrega so um `session_id` opaco -- nunca o ID
token/JWT bruto do Google. CSRF via double-submit: o cliente recebe o `csrf_token` no corpo
da resposta de login e deve devolve-lo no header `X-CSRF-Token` em toda mutacao; comparado
em tempo constante contra o segredo guardado no lado do servidor.

`SessionStore` em memoria nesta etapa (decisao do Diretor, 24/09/2026) -- reiniciar o
processo desloga todo mundo, aceitavel enquanto o item 1.6 (infraestrutura real) nao esta
provisionado. NAO declarar isto homologado/pronto para producao por causa disso; o store
persistente/compartilhado fica para quando a infraestrutura real existir.

Achado de fm-security-review (24/09/2026, WP-02), corrigido por decisao do Diretor no mesmo
dia: sem protecao, um site malicioso podia disparar `POST /auth/session` com o PROPRIO
id_token do atacante, fazendo o navegador da vitima receber um `Set-Cookie` autenticado como
o atacante ("login CSRF"/forced login) -- `SameSite=Lax` nao cobre isso (o ataque nem
depende de enviar cookie nenhum, so de o navegador processar a resposta). Mitigado com um
nonce de pre-login double-submit: `GET /auth/login-nonce` emite um cookie curto e efemero
(`LOGIN_CSRF_COOKIE_NAME`) e devolve o mesmo valor no corpo; `POST /auth/session` exige esse
valor de volta (`login_csrf_token`) e o compara em tempo constante contra o cookie -- um
site cross-origin nao consegue ler o cookie (`HttpOnly`) nem forjar o par cookie+corpo sem
ver a resposta same-origin do `GET`.
"""

from __future__ import annotations

import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from .state import TokenPrincipal

SESSION_COOKIE_NAME = "campaia_session"
CSRF_HEADER_NAME = "x-csrf-token"

#: Cookie de nonce de pre-login (double-submit), curto e de uso unico -- nunca confundir
#: com o cookie de sessao real acima. Ver nota do modulo sobre o achado de login-CSRF.
LOGIN_CSRF_COOKIE_NAME = "campaia_login_csrf"
#: Generoso o bastante para o usuario completar o fluxo de login no provedor de identidade
#: (redirect + volta), curto o bastante para nao virar um segredo de vida longa.
LOGIN_CSRF_TTL = timedelta(minutes=10)

#: Item 1.3/WP-02 (24/09/2026): TTL absoluto de 24h, alinhado a NFR 4.1
#: (docs/product/NON_FUNCTIONAL_REQUIREMENTS.md), configuravel por ambiente.
#: Deliberadamente SEM refresh silencioso nesta etapa (decisao do Diretor) -- a sessao
#: expira de verdade em 24h, exige novo login, nunca se renova sozinha em segundo plano.
DEFAULT_SESSION_TTL = timedelta(hours=24)


def _session_ttl() -> timedelta:
    hours = os.environ.get("CAMPAIA_SESSION_TTL_HOURS")
    if hours is None:
        return DEFAULT_SESSION_TTL
    return timedelta(hours=float(hours))


@dataclass(frozen=True, slots=True)
class SessionRecord:
    session_id: str
    csrf_secret: str
    principal: TokenPrincipal
    created_at: datetime
    expires_at: datetime

    def is_expired(self, *, now: datetime) -> bool:
        return now >= self.expires_at

    def csrf_token_valid(self, presented: str | None) -> bool:
        if not presented:
            return False
        return hmac.compare_digest(self.csrf_secret, presented)


class SessionStore(Protocol):
    def create(self, principal: TokenPrincipal, *, now: datetime) -> SessionRecord: ...
    def get(self, session_id: str) -> SessionRecord | None: ...
    def invalidate(self, session_id: str) -> None: ...


class InMemorySessionStore:
    """Em memoria -- ver docstring do modulo sobre por que isto e aceitavel nesta etapa."""

    def __init__(self, *, ttl: timedelta | None = None) -> None:
        self._sessions: dict[str, SessionRecord] = {}
        self._ttl = ttl if ttl is not None else _session_ttl()

    def create(self, principal: TokenPrincipal, *, now: datetime) -> SessionRecord:
        # session_id sempre novo -- nunca reaproveita um id pre-login (protecao contra
        # session fixation, exigencia literal da NFR 4.1 e do WP-02).
        record = SessionRecord(
            session_id=secrets.token_urlsafe(32),
            csrf_secret=secrets.token_urlsafe(32),
            principal=principal,
            created_at=now,
            expires_at=now + self._ttl,
        )
        self._sessions[record.session_id] = record
        return record

    def get(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    def invalidate(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


def set_session_cookie(response, session_id: str, *, max_age_seconds: int) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        max_age=max_age_seconds,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def generate_login_csrf_nonce() -> str:
    """Gera o valor do nonce de pre-login -- gerado ANTES de montar o corpo JSON da
    resposta de `GET /auth/login-nonce` (que precisa carregar o mesmo valor), depois
    gravado no cookie via `set_login_csrf_cookie`."""
    return secrets.token_urlsafe(32)


def set_login_csrf_cookie(response, nonce: str) -> None:
    """Grava o nonce de pre-login no cookie -- o cliente precisa devolver os dois (cookie
    presente automaticamente pelo navegador + o mesmo valor no corpo do `POST
    /auth/session`) para provar que viu a resposta same-origin do `GET`, o que um site
    cross-origin nao consegue forjar."""
    response.set_cookie(
        LOGIN_CSRF_COOKIE_NAME,
        nonce,
        max_age=int(LOGIN_CSRF_TTL.total_seconds()),
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def login_csrf_token_valid(request, presented: str | None) -> bool:
    """Compara em tempo constante o nonce do cookie (`LOGIN_CSRF_COOKIE_NAME`) contra o
    valor devolvido no corpo de `POST /auth/session` -- os dois precisam bater."""
    cookie_value = request.cookies.get(LOGIN_CSRF_COOKIE_NAME)
    if not cookie_value or not presented:
        return False
    return hmac.compare_digest(cookie_value, presented)


def clear_login_csrf_cookie(response) -> None:
    response.delete_cookie(LOGIN_CSRF_COOKIE_NAME, path="/")


__all__ = [
    "CSRF_HEADER_NAME",
    "DEFAULT_SESSION_TTL",
    "LOGIN_CSRF_COOKIE_NAME",
    "LOGIN_CSRF_TTL",
    "SESSION_COOKIE_NAME",
    "InMemorySessionStore",
    "SessionRecord",
    "SessionStore",
    "clear_login_csrf_cookie",
    "clear_session_cookie",
    "generate_login_csrf_nonce",
    "login_csrf_token_valid",
    "set_login_csrf_cookie",
    "set_session_cookie",
]
