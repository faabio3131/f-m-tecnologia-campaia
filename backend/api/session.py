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
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import urlsplit

from .state import TokenPrincipal

SESSION_COOKIE_NAME = "campaia_session"
CSRF_HEADER_NAME = "x-csrf-token"

#: Item 1.3/WP-02, achado de fm-security-review (24/09/2026) corrigido por decisao do
#: Diretor: login-CSRF em POST /auth/session. Defesa fail-closed por validacao de
#: Origin/Referer same-origin -- NUNCA wildcard, origem ausente/invalida/nao configurada
#: e sempre rejeitada.
ALLOWED_ORIGINS_ENV_VAR = "CAMPAIA_ALLOWED_ORIGINS"

#: Origem valida: "scheme://host" ou "scheme://host:port", scheme http/https, sem path,
#: query, fragment, espaco ou "*". Rejeita qualquer coisa fora desse formato exato.
_ORIGIN_PATTERN = re.compile(r"^https?://[A-Za-z0-9.\-]+(:\d+)?$")


def _parse_origin(value: str) -> str | None:
    value = value.strip()
    if not value or "*" in value or not _ORIGIN_PATTERN.fullmatch(value):
        return None
    return value


def parse_allowed_origins(raw: str) -> frozenset[str]:
    """Fail-closed por configuracao: se `raw` estiver vazio OU contiver qualquer entrada
    invalida (wildcard, malformada), o resultado e o conjunto vazio -- nenhuma origem e
    aceita. Nunca "confia parcialmente" numa configuracao parcialmente quebrada."""
    entries = [e for e in (part.strip() for part in raw.split(",")) if e]
    if not entries:
        return frozenset()
    parsed = [_parse_origin(e) for e in entries]
    if any(p is None for p in parsed):
        return frozenset()
    return frozenset(parsed)


def default_allowed_origins() -> frozenset[str]:
    return parse_allowed_origins(os.environ.get(ALLOWED_ORIGINS_ENV_VAR, ""))


def extract_request_origin(request) -> str | None:
    """Origin tem prioridade (enviado por fetch/XHR em todo metodo mutante, mesmo
    same-origin, desde 2017). Referer e fallback só quando Origin estiver ausente --
    nunca o contrario, e qualquer valor malformado em qualquer um dos dois vira None
    (rejeitado por quem chama, nunca tratado como "sem preferencia")."""
    origin = request.headers.get("origin")
    if origin is not None:
        return _parse_origin(origin)

    referer = request.headers.get("referer")
    if referer is not None:
        parts = urlsplit(referer)
        if parts.scheme and parts.netloc:
            return _parse_origin(f"{parts.scheme}://{parts.netloc}")
    return None


def is_same_origin(request, allowed: frozenset[str]) -> bool:
    if not allowed:
        return False  # configuracao vazia/invalida -- fail-closed, nunca permite nada
    origin = extract_request_origin(request)
    return origin is not None and origin in allowed

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
    #: WP-03 (25/09/2026): TODOS os vinculos (tenant/unidade) da identidade que fez login,
    #: capturados no momento do login (`state.identity_directory.resolve_all(email)`) --
    #: nunca reconsultado ao vivo a cada troca, mesma disciplina de nao-renovacao silenciosa
    #: ja usada para `roles`/TTL da sessao (ver docstring do modulo). Sempre inclui
    #: `principal`. Vinculo unico (caso comum ate aqui) -> tupla de 1 elemento.
    available_principals: tuple[TokenPrincipal, ...] = ()

    def is_expired(self, *, now: datetime) -> bool:
        return now >= self.expires_at

    def csrf_token_valid(self, presented: str | None) -> bool:
        if not presented:
            return False
        return hmac.compare_digest(self.csrf_secret, presented)


class SessionStore(Protocol):
    def create(
        self,
        principal: TokenPrincipal,
        *,
        now: datetime,
        available_principals: tuple[TokenPrincipal, ...] = (),
    ) -> SessionRecord: ...
    def get(self, session_id: str) -> SessionRecord | None: ...
    def invalidate(self, session_id: str) -> None: ...
    def switch_principal(
        self, session_id: str, principal: TokenPrincipal
    ) -> SessionRecord | None: ...


class InMemorySessionStore:
    """Em memoria -- ver docstring do modulo sobre por que isto e aceitavel nesta etapa."""

    def __init__(self, *, ttl: timedelta | None = None) -> None:
        self._sessions: dict[str, SessionRecord] = {}
        self._ttl = ttl if ttl is not None else _session_ttl()

    def create(
        self,
        principal: TokenPrincipal,
        *,
        now: datetime,
        available_principals: tuple[TokenPrincipal, ...] = (),
    ) -> SessionRecord:
        # session_id sempre novo -- nunca reaproveita um id pre-login (protecao contra
        # session fixation, exigencia literal da NFR 4.1 e do WP-02).
        record = SessionRecord(
            session_id=secrets.token_urlsafe(32),
            csrf_secret=secrets.token_urlsafe(32),
            principal=principal,
            created_at=now,
            expires_at=now + self._ttl,
            available_principals=available_principals or (principal,),
        )
        self._sessions[record.session_id] = record
        return record

    def get(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    def invalidate(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def switch_principal(
        self, session_id: str, principal: TokenPrincipal
    ) -> SessionRecord | None:
        """Troca o vinculo ATIVO de uma sessao ja existente, preservando `session_id` e
        `csrf_secret` (mesma sessao autenticada, so muda o tenant/unidade ativo -- o
        cliente nao precisa de um novo `csrf_token`). Quem chama e' responsavel por
        confirmar que `principal` pertence de fato a `record.available_principals` (ver
        api/routes_auth.py::switch_membership) -- este metodo nao valida isso sozinho,
        so troca o que recebe."""
        current = self._sessions.get(session_id)
        if current is None:
            return None
        updated = SessionRecord(
            session_id=current.session_id,
            csrf_secret=current.csrf_secret,
            principal=principal,
            created_at=current.created_at,
            expires_at=current.expires_at,
            available_principals=current.available_principals,
        )
        self._sessions[session_id] = updated
        return updated


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
    "ALLOWED_ORIGINS_ENV_VAR",
    "CSRF_HEADER_NAME",
    "DEFAULT_SESSION_TTL",
    "SESSION_COOKIE_NAME",
    "InMemorySessionStore",
    "SessionRecord",
    "SessionStore",
    "clear_session_cookie",
    "default_allowed_origins",
    "extract_request_origin",
    "is_same_origin",
    "parse_allowed_origins",
    "set_session_cookie",
]
