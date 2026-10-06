from __future__ import annotations

from dataclasses import dataclass

from agent_framework import Executor

from .operational_capability import OperationalCapability


class DomainExecutionBindingError(ValueError):
    """El enlace de composicion no satisface el contrato exacto."""


@dataclass(frozen=True)
class DomainExecutionBinding:
    """Enlace local entre un dominio, un ID y una instancia de Executor.

    Congela los metadatos y la referencia, no el estado del executor.
    No registra capabilities ni demuestra que una capability este instalada.
    No concede aprobacion, HITL, resource scope ni parametros operacionales.
    No ejecuta, clona o modifica el executor ni cambia el workflow.
    La autorizacion y la topologia segura siguen siendo fronteras separadas.
    """

    operation_domain: str
    executor_id: str
    executor: Executor

    def __post_init__(self) -> None:
        self._validate_exact_identifier("operation_domain", self.operation_domain)
        self._validate_exact_identifier("executor_id", self.executor_id)
        self._validate_executor_identity()

    @staticmethod
    def _validate_exact_identifier(name: str, value: object) -> None:
        if not isinstance(value, str) or not value or value != value.strip():
            raise DomainExecutionBindingError(
                f"{name} debe ser string no vacio sin espacios exteriores."
            )

    def _validate_executor_identity(self) -> None:
        if not isinstance(self.executor, Executor):
            raise DomainExecutionBindingError(
                "executor debe ser una instancia de Executor."
            )

        actual_id = getattr(self.executor, "id", None)
        self._validate_exact_identifier("executor.id", actual_id)
        if actual_id != self.executor_id:
            raise DomainExecutionBindingError(
                "executor.id no coincide exactamente con executor_id."
            )

    def resolve(self, *, capability: OperationalCapability) -> Executor:
        """Devuelve la misma instancia tras comprobar el enlace exacto.

        No normaliza identificadores, no hace fallback y no despacha.
        La coincidencia no sustituye a la autorizacion operacional.
        """
        if not isinstance(capability, OperationalCapability):
            raise DomainExecutionBindingError(
                "capability debe ser OperationalCapability."
            )

        if capability.operation_domain != self.operation_domain:
            raise DomainExecutionBindingError(
                "operation_domain de capability no coincide con el binding."
            )

        if capability.executor_id != self.executor_id:
            raise DomainExecutionBindingError(
                "executor_id de capability no coincide con el binding."
            )

        # El executor conserva su mutabilidad: comprobar de nuevo su ID.
        self._validate_executor_identity()
        return self.executor
