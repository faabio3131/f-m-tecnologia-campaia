"""Contrato canonico do Ads Connector Hub.

Invariantes materializados aqui:

  I-03  Credencial nunca transita como argumento. O conector resolve a credencial pelo
        `external_account_id` contra o cofre e recebe um SecretRef opaco, cujo repr e
        redigido. Nem log, nem excecao, nem prompt conseguem imprimir o segredo.

  I-06  Toda mutacao externa exige `idempotency_key`. Repetir o comando devolve o
        resultado original em vez de criar um segundo recurso.

  Autorizacao  Nenhuma mutacao e aceita sem `policy_decision_id`. O conector nao confia no
               chamador: ele exige a autorizacao emitida pelo Policy Engine.

  I-08  Codigo de erro de provedor NUNCA vaza para o dominio. O adaptador traduz para a
        taxonomia canonica antes de devolver.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from .errors import CampaiaError


class ConnectorErrorCode(StrEnum):
    AUTH_EXPIRED = "AUTH_EXPIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    CAPABILITY_UNSUPPORTED = "CAPABILITY_UNSUPPORTED"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    VALIDATION_REJECTED = "VALIDATION_REJECTED"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"
    TRANSIENT = "TRANSIENT"
    UNKNOWN = "UNKNOWN"


#: Erros que NAO devem ser repetidos automaticamente. Repetir so gasta cota e piora a
#: reputacao da conta - e, no caso de AUTH_EXPIRED, nunca vai funcionar sem acao humana.
NON_RETRYABLE: frozenset[ConnectorErrorCode] = frozenset(
    {
        ConnectorErrorCode.AUTH_EXPIRED,
        ConnectorErrorCode.PERMISSION_DENIED,
        ConnectorErrorCode.CAPABILITY_UNSUPPORTED,
        ConnectorErrorCode.VALIDATION_REJECTED,
        ConnectorErrorCode.POLICY_VIOLATION,
        ConnectorErrorCode.QUOTA_EXHAUSTED,
    }
)


class ConnectorError(CampaiaError):
    def __init__(
        self,
        connector_code: ConnectorErrorCode,
        message: str,
        *,
        assisted_flow_url: str | None = None,
        **details: object,
    ) -> None:
        super().__init__(message, **details)
        self.code = connector_code.value
        self.connector_code = connector_code
        #: Quando a API nao permite a acao, apontamos o portal oficial.
        #: Nunca simular sucesso (Ordem Mestra, secao 10).
        self.assisted_flow_url = assisted_flow_url

    @property
    def retryable(self) -> bool:
        return self.connector_code not in NON_RETRYABLE


class SecretRef:
    """Referencia opaca a um segredo guardado no cofre.

    O valor nunca e exposto por `repr`, `str` ou serializacao. Um segredo que aparece em
    log ou em mensagem de erro ja e um vazamento - por isso a redacao vive no tipo, e nao
    na disciplina de quem escreve o log.
    """

    __slots__ = ("_handle",)

    def __init__(self, handle: str) -> None:
        self._handle = handle

    @property
    def handle(self) -> str:
        """Identificador do segredo no cofre. NAO e o segredo."""
        return self._handle

    def __repr__(self) -> str:
        return "<SecretRef REDACTED>"

    __str__ = __repr__

    def __format__(self, spec: str) -> str:
        return repr(self)


class ConnectionMode(StrEnum):
    """Estado real da conta. A interface mostra isto ao usuario, sem maquiagem."""

    SIMULATOR = "SIMULATOR"
    TEST = "TEST"
    PRODUCTION = "PRODUCTION"


@dataclass(frozen=True)
class PublishCommand:
    tenant_id: str
    campaign_id: str
    channel: str
    external_account_id: str
    idempotency_key: str
    policy_decision_id: str
    plan_version: int
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PublishResult:
    channel: str
    external_resource_id: str
    api_version: str
    mode: ConnectionMode


class AdsConnector(Protocol):
    provider: str

    def validate_draft(self, command: PublishCommand) -> list[str]: ...
    def publish(self, command: PublishCommand) -> PublishResult: ...
    def pause(self, command: PublishCommand) -> None: ...


def require_authorization(command: PublishCommand) -> None:
    """Guarda comum a todo adaptador. Chamada antes de qualquer efeito externo."""
    if not command.policy_decision_id:
        raise ConnectorError(
            ConnectorErrorCode.PERMISSION_DENIED,
            "Mutacao externa sem policy_decision_id. O conector nao executa por confianca "
            "no chamador.",
        )
    if not command.idempotency_key:
        raise ConnectorError(
            ConnectorErrorCode.VALIDATION_REJECTED,
            "Mutacao externa sem idempotency_key.",
        )
    if not command.tenant_id:
        raise ConnectorError(
            ConnectorErrorCode.PERMISSION_DENIED, "Comando sem tenant_id."
        )
