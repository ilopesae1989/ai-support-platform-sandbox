from __future__ import annotations

from collections.abc import (
    Callable,
)

from typing import (
    Any,
)

from src.workflows.incident_resolution.operation_dispatch_ledger import (
    OperationAlreadyDispatchedError,
)


ConnectionFactory = Callable[
    [],
    Any,
]


_INSERT_CLAIM = """
INSERT INTO dbo.operation_dispatch_claims (
    operation_id
)
VALUES (
    %(operation_id)s
)
"""


_CONTAINS_CLAIM = """
SELECT TOP (1)
    1
FROM dbo.operation_dispatch_claims
WHERE operation_id = %(operation_id)s
"""


class AzureSqlOperationDispatchLedger:
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
                "un string no vacio."
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
        operation_id: str,
    ) -> None:
        self._validate_operation_id(
            operation_id
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
                    "operation_id": (
                        operation_id
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
                    OperationAlreadyDispatchedError(
                        "La operacion ya fue "
                        "despachada anteriormente. "
                        "operation_id="
                        f"{operation_id!r}."
                    )
                ) from error

            raise

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()

    def contains(
        self,
        operation_id: str,
    ) -> bool:
        self._validate_operation_id(
            operation_id
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
                    "operation_id": (
                        operation_id
                    )
                },
            )

            row = cursor.fetchone()

            return row is not None

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()