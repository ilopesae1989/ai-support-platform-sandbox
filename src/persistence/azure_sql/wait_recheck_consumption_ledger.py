from __future__ import annotations

from collections.abc import (
    Callable,
)

from typing import (
    Any,
)

from src.workflows.incident_resolution.wait_recheck_consumption_ledger import (
    WaitRecheckAlreadyConsumedError,
    WaitRecheckBeginResult,
    WaitRecheckStatus,
)


ConnectionFactory = Callable[
    [],
    Any,
]


_INSERT_CLAIM = """
INSERT INTO dbo.wait_recheck_consumption_claims (
    recheck_id
)
VALUES (
    %(recheck_id)s
)
"""


_SELECT_STATUS_FOR_UPDATE = """
SELECT TOP (1)
    status
FROM dbo.wait_recheck_consumption_claims
    WITH (UPDLOCK, HOLDLOCK)
WHERE recheck_id = %(recheck_id)s
"""


_SELECT_STATUS = """
SELECT TOP (1)
    status
FROM dbo.wait_recheck_consumption_claims
WHERE recheck_id = %(recheck_id)s
"""


_INSERT_BEGIN = """
INSERT INTO dbo.wait_recheck_consumption_claims (
    recheck_id,
    status
)
VALUES (
    %(recheck_id)s,
    %(status)s
)
"""


_UPDATE_COMPLETE = """
UPDATE dbo.wait_recheck_consumption_claims
SET
    status = %(completed_status)s
WHERE
    recheck_id = %(recheck_id)s
    AND status = %(in_progress_status)s
"""


_CONTAINS_CLAIM = """
SELECT TOP (1)
    1
FROM dbo.wait_recheck_consumption_claims
WHERE recheck_id = %(recheck_id)s
"""


class AzureSqlWaitRecheckConsumptionLedger:
    """
    Autoridad monotónica Azure SQL de WAIT.

    Estado:

        ABSENT -> IN_PROGRESS -> COMPLETED

    No realiza DDL en runtime.
    """

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
    def _validate_recheck_id(
        recheck_id: str,
    ) -> None:
        if (
            not isinstance(
                recheck_id,
                str,
            )
            or not recheck_id
            or not recheck_id.strip()
            or recheck_id
            != recheck_id.strip()
        ):
            raise ValueError(
                "recheck_id debe ser un string "
                "exacto no vacío."
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

    @staticmethod
    def _decode_status(
        row,
    ) -> WaitRecheckStatus:
        if row is None:
            raise RuntimeError(
                "WAIT status row no disponible."
            )

        try:
            return WaitRecheckStatus(
                str(
                    row[0]
                )
            )

        except ValueError as exc:
            raise RuntimeError(
                "WAIT recheck contiene status "
                "durable inválido."
            ) from exc

    def begin(
        self,
        recheck_id: str,
    ) -> WaitRecheckBeginResult:
        self._validate_recheck_id(
            recheck_id
        )

        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                _SELECT_STATUS_FOR_UPDATE,
                {
                    "recheck_id":
                        recheck_id
                },
            )

            row = cursor.fetchone()

            if row is None:
                cursor.execute(
                    _INSERT_BEGIN,
                    {
                        "recheck_id":
                            recheck_id,
                        "status": (
                            WaitRecheckStatus
                            .IN_PROGRESS
                            .value
                        ),
                    },
                )

                connection.commit()

                return (
                    WaitRecheckBeginResult
                    .CLAIMED
                )

            durable_status = (
                self._decode_status(
                    row
                )
            )

            if (
                durable_status
                == WaitRecheckStatus.IN_PROGRESS
            ):
                connection.commit()

                return (
                    WaitRecheckBeginResult
                    .RESUMED
                )

            connection.rollback()

            raise (
                WaitRecheckAlreadyConsumedError(
                    "WAIT recheck ya completado. "
                    "recheck_id="
                    f"{recheck_id!r}."
                )
            )

        except WaitRecheckAlreadyConsumedError:
            connection.rollback()
            raise

        except Exception:
            connection.rollback()
            raise

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()

    def complete(
        self,
        recheck_id: str,
    ) -> None:
        self._validate_recheck_id(
            recheck_id
        )

        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                _SELECT_STATUS_FOR_UPDATE,
                {
                    "recheck_id":
                        recheck_id
                },
            )

            row = cursor.fetchone()

            if row is None:
                connection.rollback()

                raise RuntimeError(
                    "WAIT recheck no fue iniciado. "
                    "recheck_id="
                    f"{recheck_id!r}."
                )

            durable_status = (
                self._decode_status(
                    row
                )
            )

            if (
                durable_status
                == WaitRecheckStatus.COMPLETED
            ):
                connection.commit()
                return

            cursor.execute(
                _UPDATE_COMPLETE,
                {
                    "completed_status": (
                        WaitRecheckStatus
                        .COMPLETED
                        .value
                    ),
                    "recheck_id":
                        recheck_id,
                    "in_progress_status": (
                        WaitRecheckStatus
                        .IN_PROGRESS
                        .value
                    ),
                },
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()

    def status(
        self,
        recheck_id: str,
    ) -> WaitRecheckStatus | None:
        self._validate_recheck_id(
            recheck_id
        )

        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                _SELECT_STATUS,
                {
                    "recheck_id":
                        recheck_id
                },
            )

            row = cursor.fetchone()

            if row is None:
                return None

            return self._decode_status(
                row
            )

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()

    def claim(
        self,
        recheck_id: str,
    ) -> None:
        self._validate_recheck_id(
            recheck_id
        )

        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                _INSERT_CLAIM,
                {
                    "recheck_id": (
                        recheck_id
                    )
                },
            )

            connection.commit()

        except Exception as error:
            connection.rollback()

            if self._is_integrity_error(
                connection=connection,
                error=error,
            ):
                raise (
                    WaitRecheckAlreadyConsumedError(
                        "WAIT recheck ya consumido. "
                        "recheck_id="
                        f"{recheck_id!r}."
                    )
                ) from error

            raise

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()

    def contains(
        self,
        recheck_id: str,
    ) -> bool:
        self._validate_recheck_id(
            recheck_id
        )

        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                _CONTAINS_CLAIM,
                {
                    "recheck_id": (
                        recheck_id
                    )
                },
            )

            row = cursor.fetchone()

            return row is not None

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()
