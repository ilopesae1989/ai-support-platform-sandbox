from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from agent_framework import Executor

from .domain_execution_binding import (
    DomainExecutionBinding,
    DomainExecutionBindingError,
)
from .operational_capability import OperationalCapability


@dataclass(frozen=True, init=False)
class DomainExecutionBindings:
    """Membresia local inmutable con seleccion exacta de un binding.

    Conserva referencias; no congela el estado mutable de los executors.
    No instala capabilities ni acredita conexiones o autorizacion operacional.
    No construye workflows, no clona executors y no despacha operaciones.
    """

    bindings: tuple[DomainExecutionBinding, ...]

    def __init__(self, *, bindings: Iterable[DomainExecutionBinding]) -> None:
        try:
            snapshot = tuple(bindings)
        except TypeError as exc:
            raise DomainExecutionBindingError(
                "bindings debe ser un iterable de DomainExecutionBinding."
            ) from exc

        keys: set[tuple[str, str]] = set()
        for binding in snapshot:
            if not isinstance(binding, DomainExecutionBinding):
                raise DomainExecutionBindingError(
                    "Cada miembro debe ser DomainExecutionBinding."
                )
            key = (binding.operation_domain, binding.executor_id)
            if key in keys:
                raise DomainExecutionBindingError(
                    "Binding duplicado para operation_domain y executor_id."
                )
            keys.add(key)

        object.__setattr__(self, "bindings", snapshot)

    def resolve(self, *, capability: OperationalCapability) -> Executor:
        """Selecciona por clave exacta y delega sin copiar ni hacer fallback."""
        if not isinstance(capability, OperationalCapability):
            raise DomainExecutionBindingError(
                "capability debe ser OperationalCapability."
            )

        key = (capability.operation_domain, capability.executor_id)
        for binding in self.bindings:
            if (binding.operation_domain, binding.executor_id) == key:
                # El binding seleccionado revalida tambien el ID real vigente.
                return binding.resolve(capability=capability)

        raise DomainExecutionBindingError(
            "No existe binding para operation_domain y executor_id exactos."
        )
