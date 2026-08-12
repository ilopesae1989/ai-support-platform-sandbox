from __future__ import annotations

import sqlite3

from pathlib import (
    Path,
)

from typing import (
    Protocol,
)

from .approval_correlation import (
    ApprovalCorrelationNotFoundError,
    DuplicateApprovalCorrelationError,
    PendingApprovalCorrelation,
)


class ApprovalAlreadyConsumedError(
    RuntimeError
):
    """
    La aprobación ya fue reclamada anteriormente.

    Representa replay/doble submit.

    No debe provocar una segunda respuesta al
    workflow.
    """

    pass


class PendingApprovalStore(
    Protocol
):
    """
    Persistencia de la correlación necesaria
    para reanudar una aprobación HITL.

    El store NO contiene autoridad operacional.

    Sólo conserva:

        approval_id
        workflow_id
        request_id
        checkpoint_id

    El ApprovalRequest original continúa viviendo
    en el checkpoint gobernado del workflow.
    """

    def register(
        self,
        correlation: PendingApprovalCorrelation,
    ) -> None:
        ...

    def get_by_approval_id(
        self,
        approval_id: str,
    ) -> PendingApprovalCorrelation:
        ...

    def get_by_request_id(
        self,
        request_id: str,
    ) -> PendingApprovalCorrelation:
        ...

    def claim(
        self,
        *,
        approval_id: str,
        approved: bool,
    ) -> PendingApprovalCorrelation:
        ...

    def complete(
        self,
        approval_id: str,
    ) -> None:
        ...


class SqlitePendingApprovalStore:
    """
    Implementación durable mínima para sandbox/MVP.

    Propiedades:

    - persistencia entre instancias del proceso;
    - approval_id único;
    - request_id único;
    - lookup exacto;
    - sin fuzzy matching;
    - sin fallback;
    - sin autoridad procedente del canal.

    No constituye todavía el backend distribuido
    de producción.
    """

    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
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
        connection = sqlite3.connect(
            self._database_path,
            timeout=30,
        )

        connection.row_factory = (
            sqlite3.Row
        )

        return connection

    def _initialize(
        self,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                pending_approvals (
                    approval_id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    request_id TEXT NOT NULL UNIQUE,
                    checkpoint_id TEXT NOT NULL,
                    consumption_status TEXT NOT NULL
                        DEFAULT 'pending',
                    approved_decision INTEGER NULL
                )
                """
            )

    @staticmethod
    def _validate_lookup_id(
        *,
        name: str,
        value: str,
    ) -> None:
        if (
            not isinstance(
                value,
                str,
            )
            or not value
            or not value.strip()
            or value != value.strip()
        ):
            raise ValueError(
                f"{name} debe ser un string "
                "no vacío y exacto."
            )

    @staticmethod
    def _from_row(
        row: sqlite3.Row,
    ) -> PendingApprovalCorrelation:
        return (
            PendingApprovalCorrelation(
                approval_id=(
                    row["approval_id"]
                ),

                workflow_id=(
                    row["workflow_id"]
                ),

                request_id=(
                    row["request_id"]
                ),

                checkpoint_id=(
                    row["checkpoint_id"]
                ),
            )
        )

    def register(
        self,
        correlation: PendingApprovalCorrelation,
    ) -> None:
        if not isinstance(
            correlation,
            PendingApprovalCorrelation,
        ):
            raise TypeError(
                "correlation debe ser "
                "PendingApprovalCorrelation."
            )

        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO pending_approvals (
                        approval_id,
                        workflow_id,
                        request_id,
                        checkpoint_id
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        correlation.approval_id,
                        correlation.workflow_id,
                        correlation.request_id,
                        correlation.checkpoint_id,
                    ),
                )

        except sqlite3.IntegrityError as exc:
            raise (
                DuplicateApprovalCorrelationError(
                    "La correlación HITL ya existe "
                    "para el approval_id o request_id "
                    "indicado."
                )
            ) from exc

    def get_by_approval_id(
        self,
        approval_id: str,
    ) -> PendingApprovalCorrelation:
        self._validate_lookup_id(
            name="approval_id",
            value=approval_id,
        )

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    approval_id,
                    workflow_id,
                    request_id,
                    checkpoint_id
                FROM pending_approvals
                WHERE approval_id = ?
                """,
                (
                    approval_id,
                ),
            ).fetchone()

        if row is None:
            raise (
                ApprovalCorrelationNotFoundError(
                    "No existe una aprobación "
                    "pendiente para approval_id="
                    f"{approval_id!r}."
                )
            )

        return self._from_row(
            row
        )

    def get_by_request_id(
        self,
        request_id: str,
    ) -> PendingApprovalCorrelation:
        self._validate_lookup_id(
            name="request_id",
            value=request_id,
        )

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    approval_id,
                    workflow_id,
                    request_id,
                    checkpoint_id
                FROM pending_approvals
                WHERE request_id = ?
                """,
                (
                    request_id,
                ),
            ).fetchone()

        if row is None:
            raise (
                ApprovalCorrelationNotFoundError(
                    "No existe una aprobación "
                    "pendiente para request_id="
                    f"{request_id!r}."
                )
            )

        return self._from_row(
            row
        )

    def claim(
        self,
        *,
        approval_id: str,
        approved: bool,
    ) -> PendingApprovalCorrelation:
        """
        Reclama atómicamente una aprobación pendiente.

        Sólo una ejecución puede transformar:

            pending -> claimed

        El claim vive fuera del checkpoint del workflow.

        Por tanto restaurar un checkpoint histórico
        no vuelve a habilitar una aprobación ya
        consumida.
        """

        self._validate_lookup_id(
            name="approval_id",
            value=approval_id,
        )

        if not isinstance(
            approved,
            bool,
        ):
            raise TypeError(
                "approved debe ser bool."
            )

        connection = (
            self._connect()
        )

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                """
                SELECT
                    approval_id,
                    workflow_id,
                    request_id,
                    checkpoint_id,
                    consumption_status
                FROM pending_approvals
                WHERE approval_id = ?
                """,
                (
                    approval_id,
                ),
            ).fetchone()

            if row is None:
                raise (
                    ApprovalCorrelationNotFoundError(
                        "No existe una aprobación "
                        "pendiente para approval_id="
                        f"{approval_id!r}."
                    )
                )

            if (
                row["consumption_status"]
                != "pending"
            ):
                raise (
                    ApprovalAlreadyConsumedError(
                        "La aprobación ya fue "
                        "consumida o reclamada. "
                        "approval_id="
                        f"{approval_id!r}."
                    )
                )

            cursor = connection.execute(
                """
                UPDATE pending_approvals
                SET
                    consumption_status = 'claimed',
                    approved_decision = ?
                WHERE
                    approval_id = ?
                    AND consumption_status = 'pending'
                """,
                (
                    1 if approved else 0,
                    approval_id,
                ),
            )

            if (
                cursor.rowcount
                != 1
            ):
                raise (
                    ApprovalAlreadyConsumedError(
                        "La aprobación fue reclamada "
                        "concurrentemente por otra "
                        "ejecución. approval_id="
                        f"{approval_id!r}."
                    )
                )

            connection.commit()

            return (
                PendingApprovalCorrelation(
                    approval_id=(
                        row["approval_id"]
                    ),

                    workflow_id=(
                        row["workflow_id"]
                    ),

                    request_id=(
                        row["request_id"]
                    ),

                    checkpoint_id=(
                        row["checkpoint_id"]
                    ),
                )
            )

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def complete(
        self,
        approval_id: str,
    ) -> None:
        """
        Marca como completada una aprobación que ya
        fue reclamada.

        Sólo existe transición:

            claimed -> completed
        """

        self._validate_lookup_id(
            name="approval_id",
            value=approval_id,
        )

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE pending_approvals
                SET consumption_status = 'completed'
                WHERE
                    approval_id = ?
                    AND consumption_status = 'claimed'
                """,
                (
                    approval_id,
                ),
            )

        if (
            cursor.rowcount
            != 1
        ):
            raise (
                ApprovalAlreadyConsumedError(
                    "La aprobación no se encuentra "
                    "en estado claimed y no puede "
                    "completarse. approval_id="
                    f"{approval_id!r}."
                )
            )

    def get_consumption_status(
        self,
        approval_id: str,
    ) -> str:
        """
        Observabilidad para tests/MVP.

        No concede autoridad ni cambia estado.
        """

        self._validate_lookup_id(
            name="approval_id",
            value=approval_id,
        )

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT consumption_status
                FROM pending_approvals
                WHERE approval_id = ?
                """,
                (
                    approval_id,
                ),
            ).fetchone()

        if row is None:
            raise (
                ApprovalCorrelationNotFoundError(
                    "No existe aprobación para "
                    "approval_id="
                    f"{approval_id!r}."
                )
            )

        return str(
            row["consumption_status"]
        )