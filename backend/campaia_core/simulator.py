"""Provider Simulator (ADR-0013, item 4).

Implementa o mesmo contrato dos adaptadores reais e devolve tambem as FALHAS. Um simulador
que so devolve sucesso e uma armadilha: ele faz o produto parecer pronto e esconde
exatamente os caminhos que quebram em producao.

Por isso este simulador nasce com catalogo de falhas obrigatorio e permite programar o erro
que se quer exercitar - algo que a plataforma real nao permite provocar sob demanda.

Trocar o simulador por um adaptador real e configuracao, nao reescrita.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .connectors import (
    ConnectionMode,
    ConnectorError,
    ConnectorErrorCode,
    PublishCommand,
    PublishResult,
    SecretRef,
    require_authorization,
)


@dataclass
class CallRecord:
    operation: str
    channel: str
    idempotency_key: str


@dataclass
class ProviderSimulator:
    """Adaptador falso, fiel ao contrato. Uso: desenvolvimento, testes e CI."""

    provider: str = "SIMULATOR"
    api_version: str = "sim-1"
    mode: ConnectionMode = ConnectionMode.SIMULATOR
    #: Falhas programadas por canal, consumidas em ordem a cada chamada de publish.
    scripted_failures: dict[str, list[ConnectorErrorCode]] = field(default_factory=dict)
    #: Canais sem capacidade nesta conta. Nao sao oferecidos nem simulados como sucesso.
    unsupported_channels: frozenset[str] = frozenset()
    calls: list[CallRecord] = field(default_factory=list)
    paused: list[str] = field(default_factory=list)
    #: Recursos criados, por chave de idempotencia. E o que garante que retry nao duplica.
    _created: dict[tuple[str, str], PublishResult] = field(default_factory=dict)
    _counter: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # ------------------------------------------------------------------ credencial

    def resolve_secret(self, external_account_id: str) -> SecretRef:
        """Resolve a credencial contra o cofre. Devolve referencia opaca, nunca o valor."""
        return SecretRef(handle=f"vault://{self.provider}/{external_account_id}")

    # ------------------------------------------------------------------ operacoes

    def validate_draft(self, command: PublishCommand) -> list[str]:
        """Ensaio sem efeito externo. Nao exige autorizacao porque nada muda la fora."""
        self.calls.append(CallRecord("validate_draft", command.channel, ""))
        problemas: list[str] = []
        if command.channel in self.unsupported_channels:
            problemas.append(f"Canal {command.channel} sem capacidade nesta conta.")
        if not command.payload:
            problemas.append("Payload vazio.")
        return problemas

    def publish(self, command: PublishCommand) -> PublishResult:
        require_authorization(command)
        self.calls.append(
            CallRecord("publish", command.channel, command.idempotency_key)
        )

        chave = (command.tenant_id, command.idempotency_key)
        if chave in self._created:
            return self._created[chave]  # retry nao duplica recurso externo

        if command.channel in self.unsupported_channels:
            raise ConnectorError(
                ConnectorErrorCode.CAPABILITY_UNSUPPORTED,
                f"Canal {command.channel} nao suportado nesta conta.",
                assisted_flow_url="https://portal-oficial.exemplo/ajuda",
            )

        fila = self.scripted_failures.get(command.channel)
        if fila:
            codigo = fila.pop(0)
            raise ConnectorError(codigo, f"Falha programada no canal {command.channel}.")

        self._counter[command.channel] += 1
        resultado = PublishResult(
            channel=command.channel,
            external_resource_id=(
                f"{command.channel.lower()}-{self._counter[command.channel]:04d}"
            ),
            api_version=self.api_version,
            mode=self.mode,
        )
        self._created[chave] = resultado
        return resultado

    def pause(self, command: PublishCommand) -> None:
        require_authorization(command)
        self.calls.append(CallRecord("pause", command.channel, command.idempotency_key))
        if command.channel not in self.paused:
            self.paused.append(command.channel)

    # ------------------------------------------------------------------ inspecao

    def count(self, operation: str, channel: str | None = None) -> int:
        return sum(
            1
            for c in self.calls
            if c.operation == operation and (channel is None or c.channel == channel)
        )
