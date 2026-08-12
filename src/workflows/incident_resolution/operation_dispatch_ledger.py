from __future__ import annotations

from dataclasses import (
    dataclass,
)

from threading import (
    Lock,
)

from typing import (
    Protocol,
)


class OperationAlreadyDispatchedError(
    RuntimeError
):
    """
    La operación ya fue reclamada previamente.

    Este error representa una condición de seguridad,
    no un fallo transitorio del backend.

    No debe provocar retry automático hacia Azure.
    """

    pass


class OperationDispatchLedger(
    Protocol
):
    """
    Autoridad monotónica de dispatch operacional.

    Vive fuera del estado rollbackable del workflow.

    Su responsabilidad es garantizar:

        operation_id
            ↓
        claim exactamente una vez

    El workflow puede restaurar checkpoints históricos,
    pero esa restauración no puede devolver al estado
    "no consumido" una operación ya reclamada.

    Una implementación de producción deberá usar un
    almacenamiento durable con operación atómica de
    inserción/claim.
    """

    def claim(
        self,
        operation_id: str,
    ) -> None:
        """
        Reclama operation_id de forma atómica.

        Si operation_id ya fue reclamado:
            OperationAlreadyDispatchedError
        """

        ...


@dataclass(
    frozen=True
)
class DispatchRecord:
    operation_id: str


class InMemoryOperationDispatchLedger:
    """
    Implementación determinista para tests y sandbox
    de un único proceso.

    IMPORTANTE:

    Esta implementación es monotónica respecto a los
    checkpoints del workflow porque NO forma parte del
    checkpoint.

    No pretende ser el backend durable final de
    producción.

    En producción deberá sustituirse por una
    implementación persistente compartida entre
    workers/procesos.
    """

    def __init__(self) -> None:
        self._records: dict[
            str,
            DispatchRecord,
        ] = {}

        self._lock = Lock()

    @staticmethod
    def _validate_operation_id(
        operation_id: str,
    ) -> None:
        if (
            not isinstance(
                operation_id,
                str,
            )
            or not operation_id.strip()
        ):
            raise ValueError(
                "operation_id debe ser "
                "un string no vacío."
            )

    def claim(
        self,
        operation_id: str,
    ) -> None:
        """
        Inserción atómica en memoria.

        La sección crítica cubre:

            comprobar existencia
                +
            registrar consumo

        evitando dos claims simultáneos del mismo
        operation_id dentro del proceso.
        """

        self._validate_operation_id(
            operation_id
        )

        with self._lock:
            if (
                operation_id
                in self._records
            ):
                raise (
                    OperationAlreadyDispatchedError(
                        "La operación ya fue "
                        "despachada anteriormente. "
                        "operation_id="
                        f"{operation_id!r}."
                    )
                )

            self._records[
                operation_id
            ] = DispatchRecord(
                operation_id=(
                    operation_id
                )
            )

    def contains(
        self,
        operation_id: str,
    ) -> bool:
        """
        Método de observación destinado a tests.

        No concede autoridad ni realiza transiciones.
        """

        self._validate_operation_id(
            operation_id
        )

        with self._lock:
            return (
                operation_id
                in self._records
            )

    def count(self) -> int:
        """
        Número de operations reclamadas.

        Sólo observabilidad/test.
        """

        with self._lock:
            return len(
                self._records
            )