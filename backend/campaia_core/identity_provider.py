"""Verificacao real de ID token OIDC (item 1.3 / WP-02, ADR-0018 + ADR-0022).

Mesma disciplina de `gemini_provider.py`/`asaas_gateway.py`: adaptador de infraestrutura,
nao decide nada de negocio -- so prova QUEM e o usuario (claims verificadas do Google), nunca
QUE tenant/papel ele tem (isso vem do diretorio interno, `api/identity_directory.py`).

Decisao (Diretor, 24/09/2026): usar o SDK oficial `firebase-admin` para a verificacao
criptografica do ID token, nunca reimplementar RS256/JWKS a mao -- o SDK ja cobre isso
(assinatura, `iss`, `aud`, expiracao, revogacao). `IdTokenVerifier` e o Protocol que isola o
resto do sistema desse SDK: testes injetam um verificador falso (mesmo padrao do `transport`
injetavel do `GeminiProvider`), nunca precisam de um projeto Google Cloud real.

`AlwaysRejectIdTokenVerifier` e o default enquanto o item 1.6 (projeto GCP real) nao estiver
provisionado -- diferente do simulador de IA/pagamento, aqui um "simulador permissivo" seria
um buraco de seguranca (aceitaria qualquer id_token como valido), entao o default seguro e
"nunca autentica ninguem", nao "finge que autenticou".
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


class IdentityError(Exception):
    """ID token invalido, expirado, revogado, ou verificador nao configurado.

    Fail-closed: qualquer falha de verificacao vira esta excecao unica -- quem chama nunca
    precisa (nem deve) distinguir os motivos para decidir se autentica ou nao.
    """


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    """Resultado de uma verificacao bem-sucedida. Prova QUEM (claims do Google), nunca
    tenant/papel -- isso e responsabilidade exclusiva do diretorio interno do CampaIA."""

    subject: str
    email: str
    email_verified: bool


class IdTokenVerifier(Protocol):
    def verify(self, id_token: str) -> VerifiedIdentity: ...


class AlwaysRejectIdTokenVerifier:
    """Default seguro enquanto nao houver projeto Google Cloud real (item 1.6). Nunca
    autentica ninguem -- ver docstring do modulo sobre por que isto e o default certo."""

    def verify(self, id_token: str) -> VerifiedIdentity:
        raise IdentityError(
            "Nenhum verificador de identidade real configurado (FIREBASE_PROJECT_ID "
            "ausente) -- login real esta indisponivel enquanto o item 1.6 (projeto "
            "Google Cloud) nao for provisionado."
        )


@dataclass(frozen=True, slots=True)
class FirebaseIdentityConfig:
    """Configuracao lida do ambiente -- nunca fixa em codigo, mesmo padrao de
    `GeminiConfig`/`AsaasConfig`."""

    project_id: str

    @classmethod
    def from_env(cls, prefix: str = "FIREBASE_") -> "FirebaseIdentityConfig | None":
        project_id = os.environ.get(f"{prefix}PROJECT_ID")
        if not project_id:
            return None
        return cls(project_id=project_id)


class FirebaseIdTokenVerifier:
    """Adaptador real: verifica o ID token via `firebase_admin.auth.verify_id_token`
    (SDK oficial do Google, cobre RS256/JWKS/expiracao/revogacao -- nao reimplementado
    aqui, por decisao explicita do Diretor, 24/09/2026)."""

    def __init__(self, config: FirebaseIdentityConfig, *, app_name: str | None = None) -> None:
        import firebase_admin

        self._config = config
        name = app_name or f"campaia-{config.project_id}"
        try:
            self._app = firebase_admin.get_app(name)
        except ValueError:
            self._app = firebase_admin.initialize_app(
                options={"projectId": config.project_id}, name=name
            )

    def verify(self, id_token: str) -> VerifiedIdentity:
        from firebase_admin import auth as firebase_auth

        try:
            decoded = firebase_auth.verify_id_token(id_token, app=self._app, check_revoked=True)
        except Exception as exc:  # noqa: BLE001 -- qualquer falha do SDK e fail-closed aqui
            raise IdentityError(f"ID token invalido ou expirado: {exc}") from exc

        email = decoded.get("email")
        if not email:
            raise IdentityError("ID token verificado nao contem claim 'email'.")

        return VerifiedIdentity(
            subject=str(decoded["sub"]),
            email=str(email),
            email_verified=bool(decoded.get("email_verified", False)),
        )


__all__ = [
    "AlwaysRejectIdTokenVerifier",
    "FirebaseIdTokenVerifier",
    "FirebaseIdentityConfig",
    "IdTokenVerifier",
    "IdentityError",
    "VerifiedIdentity",
]
