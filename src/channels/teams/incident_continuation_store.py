from __future__ import annotations

from contextlib import (
    closing,
)

import json
import sqlite3
import time

from enum import Enum
from pathlib import Path

from typing import (
    Protocol,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from .approval_authorization import (
    AuthorizedTeamsApprovalInvocation,
)


class IncidentContinuationConflictError(
    RuntimeError
):
    """
    El mismo approval_id ya fue persistido con
    un payload autorizado diferente.
    """

    pass


class IncidentContinuationClaimError(
    RuntimeError
):
    """
    Transición inválida del lifecycle durable.
    """

    pass


class IncidentContinuationStatus(
    str,
    Enum,
):
    PENDING = "pending"
    CLAIMED = "claimed"
    COMPLETED = "completed"
    FAILED = "failed"


class IncidentContinuationJob(
    BaseModel
):
    """
    Unidad durable posterior al ACK de Teams.

    Contiene exclusivamente una decisión HITL
    ya autenticada y autorizada.

    NO contiene autoridad operacional Azure.
    NO contiene ProcedureRuntimeState.
    NO contiene parámetros reconstruidos desde Teams.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
    )

    approval_id: str

    invocation: (
        AuthorizedTeamsApprovalInvocation
    )

    status: IncidentContinuationStatus

    attempt_count: int = 0

    claimed_by: str | None = None

    last_error: str | None = None

    created_at: float

    updated_at: float

    @field_validator(
        "approval_id"
    )
    @classmethod
    def validate_approval_id(
        cls,
        value: str,
    ) -> str:
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
                "approval_id debe ser un string "
                "no vacío y exacto."
            )

        return value

    @field_validator(
        "attempt_count"
    )
    @classmethod
    def validate_attempt_count(
        cls,
        value: int,
    ) -> int:
        if (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                int,
            )
            or value < 0
        ):
            raise ValueError(
                "attempt_count debe ser un entero "
                "mayor o igual que cero."
            )

        return value

    @model_validator(
        mode="after"
    )
    def validate_identity_and_state(
        self,
    ):
        if (
            self.approval_id
            !=
            self.invocation
            .action
            .approval_id
        ):
            raise ValueError(
                "approval_id no coincide con "
                "AuthorizedTeamsApprovalInvocation."
            )

        if (
            self.status
            == IncidentContinuationStatus.CLAIMED
        ):
            if self.claimed_by is None:
                raise ValueError(
                    "claimed requiere claimed_by."
                )

        elif self.claimed_by is not None:
            raise ValueError(
                "claimed_by sólo puede existir "
                "cuando status=claimed."
            )

        return self


class IncidentContinuationStore(
    Protocol
):
    def enqueue(
        self,
        invocation: (
            AuthorizedTeamsApprovalInvocation
        ),
    ) -> IncidentContinuationJob:
        ...

    def get(
        self,
        approval_id: str,
    ) -> IncidentContinuationJob:
        ...

    def claim_next(
        self,
        *,
        worker_id: str,
    ) -> IncidentContinuationJob | None:
        ...

    def complete(
        self,
        *,
        approval_id: str,
        worker_id: str,
    ) -> IncidentContinuationJob:
        ...

    def fail(
        self,
        *,
        approval_id: str,
        worker_id: str,
        error: str,
    ) -> IncidentContinuationJob:
        ...

    def recover_claimed_before_approval(
        self,
        *,
        approval_id: str,
        worker_id: str,
        approval_store: object,
    ) -> IncidentContinuationJob:
        ...

class SqliteIncidentContinuationStore:
    """
    Handoff durable mínimo para sandbox/MVP.

    Lifecycle monotónico:

        pending
            -> claimed
                -> completed
                -> failed

    Un job claimed NO vuelve automáticamente
    a pending.

    Esto es deliberadamente fail-closed:
    una caída del worker jamás habilita por sí
    sola una segunda ejecución operacional.

    La recuperación de un claim interrumpido
    debe correlacionarse posteriormente contra
    checkpoints y dispatch ledger durable.
    """

    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(
            database_path
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
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                incident_continuation_jobs (
                    approval_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    claimed_by TEXT NULL,
                    last_error TEXT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )

    @staticmethod
    def _validate_exact_string(
        *,
        name: str,
        value: str,
    ) -> str:
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

        return value

    @staticmethod
    def _canonical_payload(
        invocation: (
            AuthorizedTeamsApprovalInvocation
        ),
    ) -> str:
        return json.dumps(
            invocation.model_dump(
                mode="json"
            ),
            ensure_ascii=False,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        )

    @staticmethod
    def _from_row(
        row: sqlite3.Row,
    ) -> IncidentContinuationJob:
        payload = json.loads(
            row["payload_json"]
        )

        invocation = (
            AuthorizedTeamsApprovalInvocation
            .model_validate(
                payload
            )
        )

        return IncidentContinuationJob(
            approval_id=(
                row["approval_id"]
            ),

            invocation=(
                invocation
            ),

            status=(
                IncidentContinuationStatus(
                    row["status"]
                )
            ),

            attempt_count=(
                int(
                    row["attempt_count"]
                )
            ),

            claimed_by=(
                row["claimed_by"]
            ),

            last_error=(
                row["last_error"]
            ),

            created_at=(
                float(
                    row["created_at"]
                )
            ),

            updated_at=(
                float(
                    row["updated_at"]
                )
            ),
        )

    def enqueue(
        self,
        invocation: (
            AuthorizedTeamsApprovalInvocation
        ),
    ) -> IncidentContinuationJob:
        """
        Persiste antes del ACK.

        Repetir exactamente el mismo invoke
        autorizado es idempotente.

        Reutilizar approval_id con una identidad
        o decisión diferente falla cerrado.
        """

        if not isinstance(
            invocation,
            AuthorizedTeamsApprovalInvocation,
        ):
            raise TypeError(
                "invocation debe ser "
                "AuthorizedTeamsApprovalInvocation."
            )

        approval_id = (
            invocation
            .action
            .approval_id
        )

        payload_json = (
            self._canonical_payload(
                invocation
            )
        )

        now = time.time()

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
                    payload_json,
                    status,
                    attempt_count,
                    claimed_by,
                    last_error,
                    created_at,
                    updated_at
                FROM incident_continuation_jobs
                WHERE approval_id = ?
                """,
                (
                    approval_id,
                ),
            ).fetchone()

            if row is not None:
                if (
                    row["payload_json"]
                    != payload_json
                ):
                    raise (
                        IncidentContinuationConflictError(
                            "approval_id ya existe con "
                            "un payload autorizado "
                            "diferente."
                        )
                    )

                connection.commit()

                return self._from_row(
                    row
                )

            connection.execute(
                """
                INSERT INTO
                incident_continuation_jobs (
                    approval_id,
                    payload_json,
                    status,
                    attempt_count,
                    claimed_by,
                    last_error,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval_id,
                    payload_json,
                    (
                        IncidentContinuationStatus
                        .PENDING
                        .value
                    ),
                    0,
                    None,
                    None,
                    now,
                    now,
                ),
            )

            row = connection.execute(
                """
                SELECT
                    approval_id,
                    payload_json,
                    status,
                    attempt_count,
                    claimed_by,
                    last_error,
                    created_at,
                    updated_at
                FROM incident_continuation_jobs
                WHERE approval_id = ?
                """,
                (
                    approval_id,
                ),
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    "El job no quedó persistido."
                )

            connection.commit()

            return self._from_row(
                row
            )

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def get(
        self,
        approval_id: str,
    ) -> IncidentContinuationJob:
        approval_id = (
            self._validate_exact_string(
                name="approval_id",
                value=approval_id,
            )
        )

        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                """
                SELECT
                    approval_id,
                    payload_json,
                    status,
                    attempt_count,
                    claimed_by,
                    last_error,
                    created_at,
                    updated_at
                FROM incident_continuation_jobs
                WHERE approval_id = ?
                """,
                (
                    approval_id,
                ),
            ).fetchone()

        if row is None:
            raise KeyError(
                "No existe continuation job para "
                f"approval_id={approval_id!r}."
            )

        return self._from_row(
            row
        )

    def claim_next(
        self,
        *,
        worker_id: str,
    ) -> IncidentContinuationJob | None:
        """
        Reclama atómicamente un job PENDING.

        Un job CLAIMED nunca se reclama de nuevo
        automáticamente, ni siquiera tras restart.
        """

        worker_id = (
            self._validate_exact_string(
                name="worker_id",
                value=worker_id,
            )
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
                    approval_id
                FROM incident_continuation_jobs
                WHERE status = ?
                ORDER BY
                    created_at ASC,
                    approval_id ASC
                LIMIT 1
                """,
                (
                    IncidentContinuationStatus
                    .PENDING
                    .value,
                ),
            ).fetchone()

            if row is None:
                connection.commit()
                return None

            approval_id = (
                row["approval_id"]
            )

            now = time.time()

            cursor = connection.execute(
                """
                UPDATE incident_continuation_jobs
                SET
                    status = ?,
                    attempt_count =
                        attempt_count + 1,
                    claimed_by = ?,
                    updated_at = ?
                WHERE
                    approval_id = ?
                    AND status = ?
                """,
                (
                    IncidentContinuationStatus
                    .CLAIMED
                    .value,
                    worker_id,
                    now,
                    approval_id,
                    IncidentContinuationStatus
                    .PENDING
                    .value,
                ),
            )

            if cursor.rowcount != 1:
                raise (
                    IncidentContinuationClaimError(
                        "El job fue reclamado "
                        "concurrentemente."
                    )
                )

            claimed = connection.execute(
                """
                SELECT
                    approval_id,
                    payload_json,
                    status,
                    attempt_count,
                    claimed_by,
                    last_error,
                    created_at,
                    updated_at
                FROM incident_continuation_jobs
                WHERE approval_id = ?
                """,
                (
                    approval_id,
                ),
            ).fetchone()

            if claimed is None:
                raise RuntimeError(
                    "El job reclamado desapareció."
                )

            connection.commit()

            return self._from_row(
                claimed
            )

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def complete(
        self,
        *,
        approval_id: str,
        worker_id: str,
    ) -> IncidentContinuationJob:
        approval_id = (
            self._validate_exact_string(
                name="approval_id",
                value=approval_id,
            )
        )

        worker_id = (
            self._validate_exact_string(
                name="worker_id",
                value=worker_id,
            )
        )

        now = time.time()

        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE incident_continuation_jobs
                SET
                    status = ?,
                    claimed_by = NULL,
                    last_error = NULL,
                    updated_at = ?
                WHERE
                    approval_id = ?
                    AND status = ?
                    AND claimed_by = ?
                """,
                (
                    IncidentContinuationStatus
                    .COMPLETED
                    .value,
                    now,
                    approval_id,
                    IncidentContinuationStatus
                    .CLAIMED
                    .value,
                    worker_id,
                ),
            )

        if cursor.rowcount != 1:
            raise (
                IncidentContinuationClaimError(
                    "El job no está claimed por "
                    "el worker indicado."
                )
            )

        return self.get(
            approval_id
        )

    def fail(
        self,
        *,
        approval_id: str,
        worker_id: str,
        error: str,
    ) -> IncidentContinuationJob:
        approval_id = (
            self._validate_exact_string(
                name="approval_id",
                value=approval_id,
            )
        )

        worker_id = (
            self._validate_exact_string(
                name="worker_id",
                value=worker_id,
            )
        )

        error = (
            self._validate_exact_string(
                name="error",
                value=error,
            )
        )

        now = time.time()

        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE incident_continuation_jobs
                SET
                    status = ?,
                    claimed_by = NULL,
                    last_error = ?,
                    updated_at = ?
                WHERE
                    approval_id = ?
                    AND status = ?
                    AND claimed_by = ?
                """,
                (
                    IncidentContinuationStatus
                    .FAILED
                    .value,
                    error,
                    now,
                    approval_id,
                    IncidentContinuationStatus
                    .CLAIMED
                    .value,
                    worker_id,
                ),
            )

        if cursor.rowcount != 1:
            raise (
                IncidentContinuationClaimError(
                    "El job no está claimed por "
                    "el worker indicado."
                )
            )

        return self.get(
            approval_id
        )
    def recover_claimed_before_approval(
        self,
        *,
        approval_id: str,
        worker_id: str,
        approval_store,
    ) -> IncidentContinuationJob:
        """
        Recuperación estrictamente limitada a la
        ventana previa al consumo HITL.

        Única transición permitida:

            continuation=claimed
            approval=pending
            approved_decision=None
                ->
            continuation=pending

        La seguridad depende del contrato certificado
        del incident approval processor:

            approval store claim
                ANTES DE
            workflow.run(responses=...)

        Por tanto, si la aprobación continúa pending,
        ese intento no pudo haber entregado la respuesta
        HITL al workflow y no pudo llegar al dispatch.

        No recupera:
        - approval claimed;
        - approval completed;
        - decisión ya persistida;
        - otro worker;
        - estados completed/failed/pending.

        No inspecciona ni modifica Azure/MCP/checkpoints.
        """

        approval_id = (
            self._validate_exact_string(
                name="approval_id",
                value=approval_id,
            )
        )

        worker_id = (
            self._validate_exact_string(
                name="worker_id",
                value=worker_id,
            )
        )

        get_record = getattr(
            approval_store,
            "get_consumption_record",
            None,
        )

        if not callable(
            get_record
        ):
            raise TypeError(
                "approval_store debe exponer "
                "get_consumption_record callable."
            )

        approval_status, approved_decision = (
            get_record(
                approval_id
            )
        )

        if (
            approval_status != "pending"
            or approved_decision is not None
        ):
            raise (
                IncidentContinuationClaimError(
                    "Recovery bloqueado: la aprobación "
                    "ya no está pending sin decisión."
                )
            )

        now = time.time()

        with (
            closing(
                self._connect()
            ) as connection,
            connection
        ):
            cursor = connection.execute(
                """
                UPDATE incident_continuation_jobs
                SET
                    status = ?,
                    claimed_by = NULL,
                    last_error = NULL,
                    updated_at = ?
                WHERE
                    approval_id = ?
                    AND status = ?
                    AND claimed_by = ?
                """,
                (
                    IncidentContinuationStatus
                    .PENDING
                    .value,
                    now,
                    approval_id,
                    IncidentContinuationStatus
                    .CLAIMED
                    .value,
                    worker_id,
                ),
            )

            if cursor.rowcount != 1:
                raise (
                    IncidentContinuationClaimError(
                        "Recovery bloqueado: el "
                        "continuation job no está "
                        "claimed por el worker exacto."
                    )
                )

        return self.get(
            approval_id
        )
