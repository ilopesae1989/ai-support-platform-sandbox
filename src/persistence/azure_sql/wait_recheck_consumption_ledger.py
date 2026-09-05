from __future__ import annotations

from collections.abc import (
    Callable,
)

from typing import (
    Any,
)

from src.workflows.incident_resolution.wait_recheck_consumption_ledger import (
    WaitRecheckAlreadyConsumedError,
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


_CONTAINS_CLAIM = """
SELECT TOP (1)
    1
FROM dbo.wait_recheck_consumption_claims
WHERE recheck_id = %(recheck_id)s
"""


class AzureSqlWaitRecheckConsumptionLedger:
    """
    Autoridad monotónica Azure SQL de consumo WAIT.

    No crea ni modifica schema.

    La unicidad durable pertenece a la PRIMARY KEY
    de dbo.wait_recheck_consumption_claims.
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
