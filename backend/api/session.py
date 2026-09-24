"""Sessao server-side real (ADR-0018, item 1.3/WP-02).

Cookie `HttpOnly`/`Secure`/`SameSite=Lax` carrega so um `session_id` opaco -- nunca o ID
token/JWT bruto do Google. CSRF via double-submit: o cliente recebe o `csrf_token` no corpo
da resposta de login e deve devolve-lo no header `X-CSRF-Token` em toda mutacao; comparado
em tempo constante contra o segredo guardado no lado do servidor.

`SessionStore` em memoria nesta etapa (decisao do Diretor, 24/09/2026) -- reiniciar o
processo desloga todo mundo, aceitavel enquanto o item 1.6 (infraestrutura real) nao esta
provisionado. NAO declarar isto homologado/pronto para producao por causa disso; o store
persistente/compartilhado fica para quando a infraestrutura real existir.
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


__all__ = [
    "CSRF_HEADER_NAME",
    "DEFAULT_SESSION_TTL",
    "SESSION_COOKIE_NAME",
    "InMemorySessionStore",
    "SessionRecord",
    "SessionStore",
    "clear_session_cookie",
    "set_session_cookie",
]
