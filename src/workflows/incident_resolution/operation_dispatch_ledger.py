from __future__ import annotations

from contextlib import (
    closing,
)

from dataclasses import (
    dataclass,
)

from threading import (
    Lock,
)

from typing import (
    Protocol,
)


import sqlite3
from pathlib import (
    Path,
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

    def contains(
        self,
        operation_id: str,
    ) -> bool:
        """
        Observación read-only del consumo de operation_id.

        No reclama ni libera ninguna operación.
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


class SqliteOperationDispatchLedger:
    """
    Autoridad durable mínima de dispatch para
    sandbox/MVP.

    Propiedades:

    - persistencia entre instancias/procesos;
    - operation_id único;
    - claim atómico;
    - replay fail-closed;
    - autoridad externa a checkpoints;
    - ninguna operación de delete/reset/reopen.

    Una fila persistida significa que la operación
    ya fue despachada y no puede volver a reclamarse.
    """

    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        if not isinstance(
            database_path,
            (
                str,
                Path,
            ),
        ):
            raise TypeError(
                "database_path debe ser str o Path."
            )

        if isinstance(
            database_path,
            str,
        ):
            if (
                not database_path
                or not database_path.strip()
                or (
                    database_path
                    != database_path.strip()
                )
            ):
                raise ValueError(
                    "database_path debe ser "
                    "un path no vacío y exacto."
                )

        self._database_path = (
            Path(
                database_path
            )
        )

        self._database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize()

    def _connect(
        self,
    ) -> sqlite3.Connection:
        return sqlite3.connect(
            self._database_path,
            timeout=30,
        )

    def _initialize(
        self,
    ) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                operation_dispatch_claims (
                    operation_id TEXT PRIMARY KEY
                )
                """
            )

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
        Reclama operation_id de forma durable
        y atómica.

        Sólo una ejecución puede insertar una fila
        concreta.

        Si la clave ya existe, el evento representa
        replay y se transforma en
        OperationAlreadyDispatchedError.
        """

        self._validate_operation_id(
            operation_id
        )

        connection = (
            self._connect()
        )

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            connection.execute(
                """
                INSERT INTO operation_dispatch_claims (
                    operation_id
                )
                VALUES (?)
                """,
                (
                    operation_id,
                ),
            )

            connection.commit()

        except sqlite3.IntegrityError as exc:
            connection.rollback()

            raise (
                OperationAlreadyDispatchedError(
                    "La operación ya fue "
                    "despachada anteriormente. "
                    "operation_id="
                    f"{operation_id!r}."
                )
            ) from exc

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def contains(
        self,
        operation_id: str,
    ) -> bool:
        """
        Comprueba durablemente si operation_id
        ya fue reclamado.

        Es estrictamente read-only.
        """

        self._validate_operation_id(
            operation_id
        )

        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                """
                SELECT 1
                FROM operation_dispatch_claims
                WHERE operation_id = ?
                LIMIT 1
                """,
                (
                    operation_id,
                ),
            ).fetchone()

        return row is not None
