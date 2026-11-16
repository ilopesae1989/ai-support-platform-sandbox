from __future__ import annotations

from collections.abc import (
    Callable,
)

import time

from typing import (
    Any,
)

from src.runtime.procedure.authorized_approval import AuthorizedApprovalInvocation
from src.runtime.incident_continuation_codec import ContinuationPayloadCodec

from src.runtime.incident_continuation_store import (
    IncidentContinuationClaimError,
    IncidentContinuationConflictError,
    IncidentContinuationJob,
    IncidentContinuationStatus,
)


ConnectionFactory = Callable[
    [],
    Any,
]


_JOB_COLUMNS = """
    approval_id,
    payload_json,
    status,
    attempt_count,
    claimed_by,
    last_error,
    created_at,
    updated_at
"""


_INSERT_JOB = """
INSERT INTO dbo.incident_continuation_jobs (
    approval_id,
    payload_json,
    status,
    attempt_count,
    claimed_by,
    last_error,
    created_at,
    updated_at
)
OUTPUT
    inserted.approval_id,
    inserted.payload_json,
    inserted.status,
    inserted.attempt_count,
    inserted.claimed_by,
    inserted.last_error,
    inserted.created_at,
    inserted.updated_at
VALUES (
    %(approval_id)s,
    %(payload_json)s,
    %(status)s,
    %(attempt_count)s,
    %(claimed_by)s,
    %(last_error)s,
    %(created_at)s,
    %(updated_at)s
)
"""


_SELECT_JOB = """
SELECT
    approval_id,
    payload_json,
    status,
    attempt_count,
    claimed_by,
    last_error,
    created_at,
    updated_at
FROM dbo.incident_continuation_jobs
WHERE approval_id = %(approval_id)s
"""


_CLAIM_NEXT = """
;WITH next_job AS (
    SELECT TOP (1)
        approval_id,
        payload_json,
        status,
        attempt_count,
        claimed_by,
        last_error,
        created_at,
        updated_at
    FROM dbo.incident_continuation_jobs
        WITH (
            UPDLOCK,
            READPAST,
            READCOMMITTEDLOCK,
            ROWLOCK
        )
    WHERE status = 'pending'
    ORDER BY
        created_at ASC,
        approval_id ASC
)
UPDATE next_job
SET
    status = 'claimed',
    attempt_count = attempt_count + 1,
    claimed_by = %(worker_id)s,
    updated_at = %(updated_at)s
OUTPUT
    inserted.approval_id,
    inserted.payload_json,
    inserted.status,
    inserted.attempt_count,
    inserted.claimed_by,
    inserted.last_error,
    inserted.created_at,
    inserted.updated_at
"""


_COMPLETE_JOB = """
UPDATE dbo.incident_continuation_jobs
SET
    status = 'completed',
    claimed_by = NULL,
    last_error = NULL,
    updated_at = %(updated_at)s
OUTPUT
    inserted.approval_id,
    inserted.payload_json,
    inserted.status,
    inserted.attempt_count,
    inserted.claimed_by,
    inserted.last_error,
    inserted.created_at,
    inserted.updated_at
WHERE
    approval_id = %(approval_id)s
    AND status = 'claimed'
    AND claimed_by = %(worker_id)s
"""


_FAIL_JOB = """
UPDATE dbo.incident_continuation_jobs
SET
    status = 'failed',
    claimed_by = NULL,
    last_error = %(error)s,
    updated_at = %(updated_at)s
OUTPUT
    inserted.approval_id,
    inserted.payload_json,
    inserted.status,
    inserted.attempt_count,
    inserted.claimed_by,
    inserted.last_error,
    inserted.created_at,
    inserted.updated_at
WHERE
    approval_id = %(approval_id)s
    AND status = 'claimed'
    AND claimed_by = %(worker_id)s
"""


_RECOVERY_APPROVAL_GUARD = """
SELECT
    consumption_status,
    approved_decision
FROM dbo.pending_approvals
    WITH (
        UPDLOCK,
        HOLDLOCK
    )
WHERE approval_id = %(approval_id)s
"""


_RECOVER_JOB = """
UPDATE dbo.incident_continuation_jobs
SET
    status = 'pending',
    claimed_by = NULL,
    last_error = NULL,
    updated_at = %(updated_at)s
OUTPUT
    inserted.approval_id,
    inserted.payload_json,
    inserted.status,
    inserted.attempt_count,
    inserted.claimed_by,
    inserted.last_error,
    inserted.created_at,
    inserted.updated_at
WHERE
    approval_id = %(approval_id)s
    AND status = 'claimed'
    AND claimed_by = %(worker_id)s
"""


def _require_exact_string(
    *,
    name: str,
    value: object,
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
            "exacto no vacio."
        )

    return value


def _job_from_row(
    row: Any,
    *,
    payload_codec: ContinuationPayloadCodec,
) -> IncidentContinuationJob:
    invocation = payload_codec.decode(row[1])

    return IncidentContinuationJob[payload_codec.invocation_type](
        approval_id=row[0],
        invocation=invocation,
        status=IncidentContinuationStatus(
            row[2]
        ),
        attempt_count=int(
            row[3]
        ),
        claimed_by=row[4],
        last_error=row[5],
        created_at=float(
            row[6]
        ),
        updated_at=float(
            row[7]
        ),
    )


class AzureSqlIncidentContinuationStore:
    def __init__(
        self,
        *,
        connection_factory: ConnectionFactory,
        payload_codec: ContinuationPayloadCodec,
    ) -> None:
        if not callable(
            connection_factory
        ):
            raise TypeError(
                "connection_factory debe ser callable."
            )

        if not isinstance(payload_codec, ContinuationPayloadCodec):
            raise TypeError("Explicit continuation payload codec required.")
        self._payload_codec = payload_codec

        self._connection_factory = (
            connection_factory
        )

    @staticmethod
    def _is_integrity_error(
        *,
        connection: Any,
        error: Exception,
    ) -> bool:
        integrity_error_type = getattr(
            connection,
            "IntegrityError",
            None,
        )

        if not isinstance(
            integrity_error_type,
            type,
        ):
            return False

        return isinstance(
            error,
            integrity_error_type,
        )

    def enqueue(
        self,
        invocation: AuthorizedApprovalInvocation,
    ) -> IncidentContinuationJob:
        if not isinstance(
            invocation,
            self._payload_codec.invocation_type,
        ):
            raise TypeError(
                "invocation must match the configured authorized model."
            )

        approval_id = (
            invocation.action.approval_id
        )

        payload_json = (
            self._payload_codec.encode(
                invocation
            )
        )

        now = time.time()

        parameters = {
            "approval_id": approval_id,
            "payload_json": payload_json,
            "status": "pending",
            "attempt_count": 0,
            "claimed_by": None,
            "last_error": None,
            "created_at": now,
            "updated_at": now,
        }

        connection = (
            self._connection_factory()
        )

        cursor = None

        rollback_performed = False

        try:
            cursor = connection.cursor()

            try:
                cursor.execute(
                    _INSERT_JOB,
                    parameters,
                )

                inserted = cursor.fetchone()

            except Exception as error:
                if not self._is_integrity_error(
                    connection=connection,
                    error=error,
                ):
                    raise

                connection.rollback()

                rollback_performed = True

                cursor.execute(
                    _SELECT_JOB,
                    {
                        "approval_id": (
                            approval_id
                        )
                    },
                )

                existing = cursor.fetchone()

                if existing is None:
                    raise (
                        IncidentContinuationConflictError(
                            "approval_id duplicado sin "
                            "fila durable recuperable."
                        )
                    ) from error

                existing_job = (
                    _job_from_row(existing, payload_codec=self._payload_codec)
                )

                if (
                    self._payload_codec.encode(
                        existing_job.invocation
                    )
                    != payload_json
                ):
                    raise (
                        IncidentContinuationConflictError(
                            "approval_id ya existe "
                            "con payload autorizado "
                            "diferente."
                        )
                    ) from error

                return existing_job

            if inserted is None:
                raise RuntimeError(
                    "El job insertado no fue "
                    "devuelto por OUTPUT."
                )

            connection.commit()

            return _job_from_row(inserted, payload_codec=self._payload_codec)

        except Exception:
            if not rollback_performed:
                connection.rollback()

            raise

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()

    def get(
        self,
        approval_id: str,
    ) -> IncidentContinuationJob:
        approval_id = _require_exact_string(
            name="approval_id",
            value=approval_id,
        )

        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                _SELECT_JOB,
                {
                    "approval_id": (
                        approval_id
                    )
                },
            )

            row = cursor.fetchone()

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()

        if row is None:
            raise KeyError(
                "No existe continuation job para "
                f"approval_id={approval_id!r}."
            )

        return _job_from_row(row, payload_codec=self._payload_codec)

    def claim_next(
        self,
        *,
        worker_id: str,
    ) -> IncidentContinuationJob | None:
        worker_id = _require_exact_string(
            name="worker_id",
            value=worker_id,
        )

        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                _CLAIM_NEXT,
                {
                    "worker_id": (
                        worker_id
                    ),
                    "updated_at": (
                        time.time()
                    ),
                },
            )

            claimed = cursor.fetchone()

            connection.commit()

            if claimed is None:
                return None

            return _job_from_row(claimed, payload_codec=self._payload_codec)

        except Exception:
            connection.rollback()
            raise

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()

    def complete(
        self,
        *,
        approval_id: str,
        worker_id: str,
    ) -> IncidentContinuationJob:
        approval_id = _require_exact_string(
            name="approval_id",
            value=approval_id,
        )

        worker_id = _require_exact_string(
            name="worker_id",
            value=worker_id,
        )

        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                _COMPLETE_JOB,
                {
                    "approval_id": (
                        approval_id
                    ),
                    "worker_id": (
                        worker_id
                    ),
                    "updated_at": (
                        time.time()
                    ),
                },
            )

            completed = cursor.fetchone()

            if completed is None:
                raise (
                    IncidentContinuationClaimError(
                        "El job no esta claimed por "
                        "el worker indicado."
                    )
                )

            connection.commit()

            return _job_from_row(completed, payload_codec=self._payload_codec)

        except Exception:
            connection.rollback()
            raise

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()

    def fail(
        self,
        *,
        approval_id: str,
        worker_id: str,
        error: str,
    ) -> IncidentContinuationJob:
        approval_id = _require_exact_string(
            name="approval_id",
            value=approval_id,
        )

        worker_id = _require_exact_string(
            name="worker_id",
            value=worker_id,
        )

        error = _require_exact_string(
            name="error",
            value=error,
        )

        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                _FAIL_JOB,
                {
                    "approval_id": (
                        approval_id
                    ),
                    "worker_id": (
                        worker_id
                    ),
                    "error": error,
                    "updated_at": (
                        time.time()
                    ),
                },
            )

            failed = cursor.fetchone()

            if failed is None:
                raise (
                    IncidentContinuationClaimError(
                        "El job no esta claimed por "
                        "el worker indicado."
                    )
                )

            connection.commit()

            return _job_from_row(failed, payload_codec=self._payload_codec)

        except Exception:
            connection.rollback()
            raise

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()

    def recover_claimed_before_approval(
        self,
        *,
        approval_id: str,
        worker_id: str,
        approval_store: object,
    ) -> IncidentContinuationJob:
        approval_id = _require_exact_string(
            name="approval_id",
            value=approval_id,
        )

        worker_id = _require_exact_string(
            name="worker_id",
            value=worker_id,
        )

        get_consumption_record = getattr(
            approval_store,
            "get_consumption_record",
            None,
        )

        if not callable(
            get_consumption_record
        ):
            raise TypeError(
                "approval_store debe exponer "
                "get_consumption_record."
            )

        status, approved = (
            get_consumption_record(
                approval_id
            )
        )

        if (
            status != "pending"
            or approved is not None
        ):
            raise (
                IncidentContinuationClaimError(
                    "La aprobacion ya fue "
                    "consumida o decidida."
                )
            )

        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                _RECOVERY_APPROVAL_GUARD,
                {
                    "approval_id": (
                        approval_id
                    )
                },
            )

            guard_row = cursor.fetchone()

            if (
                guard_row is None
                or guard_row[0] != "pending"
                or guard_row[1] is not None
            ):
                raise (
                    IncidentContinuationClaimError(
                        "La aprobacion dejo de estar "
                        "pending antes del recovery."
                    )
                )

            cursor.execute(
                _RECOVER_JOB,
                {
                    "approval_id": (
                        approval_id
                    ),
                    "worker_id": (
                        worker_id
                    ),
                    "updated_at": (
                        time.time()
                    ),
                },
            )

            recovered = cursor.fetchone()

            if recovered is None:
                raise (
                    IncidentContinuationClaimError(
                        "El continuation job no esta "
                        "claimed por el worker indicado."
                    )
                )

            connection.commit()

            return _job_from_row(recovered, payload_codec=self._payload_codec)

        except Exception:
            connection.rollback()
            raise

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()