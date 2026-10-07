from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from agent_framework import Executor

from .domain_execution_binding import DomainExecutionBinding


class DomainExecutionPathError(ValueError):
    """El tramo declarado no conserva su estructura o identidad exacta."""


@dataclass(frozen=True, init=False)
class DomainExecutionPath:
    """Tramo lineal declarado desde una entrada hasta el executor enlazado.

    Conserva referencias e IDs; no congela el estado de los executors.
    No verifica seguridad de handlers, tipos de mensajes o conexion al grafo.
    No resuelve capabilities, concede autoridad, construye aristas del SDK,
    clona componentes ni ejecuta operaciones. No representa el dominio entero.
    """

    execution_binding: DomainExecutionBinding
    executors: tuple[Executor, ...]
    _executor_ids: tuple[str, ...] = field(repr=False)

    def __init__(
        self,
        *,
        execution_binding: DomainExecutionBinding,
        executors: Iterable[Executor],
    ) -> None:
        if not isinstance(execution_binding, DomainExecutionBinding):
            raise DomainExecutionPathError(
                "execution_binding debe ser DomainExecutionBinding."
            )
        try:
            snapshot = tuple(executors)
        except TypeError as exc:
            raise DomainExecutionPathError(
                "executors debe ser un iterable de Executor."
            ) from exc

        object.__setattr__(self, "execution_binding", execution_binding)
        object.__setattr__(self, "executors", snapshot)
        object.__setattr__(self, "_executor_ids", self._current_ids())

    def _current_ids(self) -> tuple[str, ...]:
        if len(self.executors) < 2:
            raise DomainExecutionPathError(
                "El tramo requiere entrada previa y executor operacional final."
            )
        ids: list[str] = []
        references: set[int] = set()
        for executor in self.executors:
            if not isinstance(executor, Executor):
                raise DomainExecutionPathError("Cada miembro debe ser Executor.")
            executor_id = getattr(executor, "id", None)
            if (
                not isinstance(executor_id, str)
                or not executor_id
                or executor_id != executor_id.strip()
            ):
                raise DomainExecutionPathError(
                    "executor.id debe ser string no vacio sin espacios exteriores."
                )
            if id(executor) in references or executor_id in ids:
                raise DomainExecutionPathError("Referencia o ID duplicado en el tramo.")
            references.add(id(executor))
            ids.append(executor_id)

        if self.executors[-1] is not self.execution_binding.executor:
            raise DomainExecutionPathError(
                "El ultimo miembro debe ser la instancia exacta del binding."
            )
        if ids[-1] != self.execution_binding.executor_id:
            raise DomainExecutionPathError(
                "El ID operacional no coincide exactamente con el binding."
            )
        return tuple(ids)

    def validate(self) -> None:
        """Revalida estructura e IDs vigentes sin reparar cambios ni ejecutar."""
        if self._current_ids() != self._executor_ids:
            raise DomainExecutionPathError("Un ID del tramo cambio tras su declaracion.")

    @property
    def entry(self) -> Executor:
        self.validate()
        return self.executors[0]

    @property
    def edges(self) -> tuple[tuple[Executor, Executor], ...]:
        self.validate()
        return tuple(zip(self.executors, self.executors[1:]))
