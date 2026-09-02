from __future__ import annotations

from collections.abc import (
    Callable,
)

from typing import (
    Any,
)

from src.runtime.procedure.approval_correlation import (
    ApprovalCorrelationNotFoundError,
    DuplicateApprovalCorrelationError,
    PendingApprovalCorrelation,
)

from src.runtime.procedure.approval_store import (
    ApprovalAlreadyConsumedError,
)


ConnectionFactory = Callable[
    [],
    Any,
]


_INSERT_PENDING_APPROVAL = """
INSERT INTO dbo.pending_approvals (
    approval_id,
    workflow_id,
    request_id,
    checkpoint_id,
    consumption_status,
    approved_decision
)
VALUES (
    %(approval_id)s,
    %(workflow_id)s,
    %(request_id)s,
    %(checkpoint_id)s,
    'pending',
    NULL
)
"""


_SELECT_BY_APPROVAL_ID = """
SELECT
    approval_id,
    workflow_id,
    request_id,
    checkpoint_id
FROM dbo.pending_approvals
WHERE approval_id = %(approval_id)s
"""


_SELECT_BY_REQUEST_ID = """
SELECT
    approval_id,
    workflow_id,
    request_id,
    checkpoint_id
FROM dbo.pending_approvals
WHERE request_id = %(request_id)s
"""


_CLAIM_PENDING_APPROVAL = """
UPDATE dbo.pending_approvals
SET
    consumption_status = 'claimed',
    approved_decision = %(approved_decision)s
OUTPUT
    inserted.approval_id,
    inserted.workflow_id,
    inserted.request_id,
    inserted.checkpoint_id
WHERE approval_id = %(approval_id)s
  AND consumption_status = 'pending'
"""


_SELECT_CLAIM_DIAGNOSTIC = """
SELECT
    consumption_status
FROM dbo.pending_approvals
WHERE approval_id = %(approval_id)s
"""


_COMPLETE_CLAIMED_APPROVAL = """
UPDATE dbo.pending_approvals
SET
    consumption_status = 'completed'
OUTPUT
    inserted.approval_id
WHERE approval_id = %(approval_id)s
  AND consumption_status = 'claimed'
"""


_SELECT_CONSUMPTION_RECORD = """
SELECT
    consumption_status,
    approved_decision
FROM dbo.pending_approvals
WHERE approval_id = %(approval_id)s
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


def _correlation_from_row(
    row: Any,
) -> PendingApprovalCorrelation:
    return PendingApprovalCorrelation(
        approval_id=row[0],
        workflow_id=row[1],
        request_id=row[2],
        checkpoint_id=row[3],
    )


class AzureSqlPendingApprovalStore:
    def __init__(
        self,
        *,
        connection_factory: ConnectionFactory,
    ) -> None:
        if not callable(
            connection_factory
        ):
            raise TypeError(
                "connection_factory debe ser callable."
            )

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

        parameters = {
            "approval_id": (
                correlation.approval_id
            ),
            "workflow_id": (
                correlation.workflow_id
            ),
            "request_id": (
                correlation.request_id
            ),
            "checkpoint_id": (
                correlation.checkpoint_id
            ),
        }

        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                _INSERT_PENDING_APPROVAL,
                parameters,
            )

            connection.commit()

        except Exception as error:
            connection.rollback()

            if self._is_integrity_error(
                connection=connection,
                error=error,
            ):
                raise (
                    DuplicateApprovalCorrelationError(
                        "La correlacion HITL ya existe "
                        "para approval_id o request_id."
                    )
                ) from error

            raise

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()

    def get_by_approval_id(
        self,
        approval_id: str,
    ) -> PendingApprovalCorrelation:
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
                _SELECT_BY_APPROVAL_ID,
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
            raise ApprovalCorrelationNotFoundError(
                "No existe aprobacion para "
                f"approval_id={approval_id!r}."
            )

        return _correlation_from_row(
            row
        )

    def get_by_request_id(
        self,
        request_id: str,
    ) -> PendingApprovalCorrelation:
        request_id = _require_exact_string(
            name="request_id",
            value=request_id,
        )

        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                _SELECT_BY_REQUEST_ID,
                {
                    "request_id": (
                        request_id
                    )
                },
            )

            row = cursor.fetchone()

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()

        if row is None:
            raise ApprovalCorrelationNotFoundError(
                "No existe aprobacion para "
                f"request_id={request_id!r}."
            )

        return _correlation_from_row(
            row
        )

    def claim(
        self,
        *,
        approval_id: str,
        approved: bool,
    ) -> PendingApprovalCorrelation:
        approval_id = _require_exact_string(
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

        parameters = {
            "approval_id": (
                approval_id
            ),
            "approved_decision": (
                1
                if approved
                else 0
            ),
        }

        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                _CLAIM_PENDING_APPROVAL,
                parameters,
            )

            claimed_row = (
                cursor.fetchone()
            )

            if claimed_row is not None:
                connection.commit()

                return _correlation_from_row(
                    claimed_row
                )

            cursor.execute(
                _SELECT_CLAIM_DIAGNOSTIC,
                {
                    "approval_id": (
                        approval_id
                    )
                },
            )

            diagnostic_row = (
                cursor.fetchone()
            )

            if diagnostic_row is None:
                raise (
                    ApprovalCorrelationNotFoundError(
                        "No existe aprobacion para "
                        "approval_id="
                        f"{approval_id!r}."
                    )
                )

            raise ApprovalAlreadyConsumedError(
                "La aprobacion ya fue consumida "
                "o reclamada. approval_id="
                f"{approval_id!r}."
            )

        except Exception:
            connection.rollback()
            raise

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()

    def complete(
        self,
        approval_id: str,
    ) -> None:
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
                _COMPLETE_CLAIMED_APPROVAL,
                {
                    "approval_id": (
                        approval_id
                    )
                },
            )

            completed_row = (
                cursor.fetchone()
            )

            if completed_row is None:
                raise (
                    ApprovalAlreadyConsumedError(
                        "La aprobacion no se encuentra "
                        "en estado claimed. "
                        "approval_id="
                        f"{approval_id!r}."
                    )
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()

    def get_consumption_record(
        self,
        approval_id: str,
    ) -> tuple[str, bool | None]:
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
                _SELECT_CONSUMPTION_RECORD,
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
            raise ApprovalCorrelationNotFoundError(
                "No existe aprobacion para "
                f"approval_id={approval_id!r}."
            )

        status = str(
            row[0]
        )

        if status not in {
            "pending",
            "claimed",
            "completed",
        }:
            raise RuntimeError(
                "consumption_status durable "
                f"no soportado: {status!r}."
            )

        raw_decision = row[1]

        if raw_decision is None:
            approved = None

        elif raw_decision == 1:
            approved = True

        elif raw_decision == 0:
            approved = False

        else:
            raise RuntimeError(
                "approved_decision durable "
                "contiene un valor invalido."
            )

        if (
            status == "pending"
            and approved is not None
        ):
            raise RuntimeError(
                "Una aprobacion pending no puede "
                "contener approved_decision."
            )

        if (
            status in {
                "claimed",
                "completed",
            }
            and approved is None
        ):
            raise RuntimeError(
                "Una aprobacion consumida debe "
                "conservar approved_decision."
            )

        return (
            status,
            approved,
        )