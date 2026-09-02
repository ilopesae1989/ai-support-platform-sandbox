from __future__ import annotations

from collections.abc import (
    Callable,
)

from typing import (
    Any,
)

from src.channels.teams.conversation_binding import (
    TeamsConversationBinding,
)

from src.channels.teams.conversation_binding_store import (
    TeamsConversationBindingNotFoundError,
)


ConnectionFactory = Callable[
    [],
    Any,
]


_UPDATE_BINDING = """
UPDATE dbo.teams_conversation_bindings
WITH (UPDLOCK, SERIALIZABLE)
SET service_url = %(service_url)s
WHERE tenant_id = %(tenant_id)s
  AND conversation_id = %(conversation_id)s
"""


_INSERT_BINDING = """
INSERT INTO dbo.teams_conversation_bindings (
    tenant_id,
    conversation_id,
    service_url
)
VALUES (
    %(tenant_id)s,
    %(conversation_id)s,
    %(service_url)s
)
"""


_GET_EXACT_BINDING = """
SELECT
    tenant_id,
    conversation_id,
    service_url
FROM dbo.teams_conversation_bindings
WHERE tenant_id = %(tenant_id)s
  AND conversation_id = %(conversation_id)s
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


class AzureSqlTeamsConversationBindingStore:
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
    def _validate_binding(
        binding: TeamsConversationBinding,
    ) -> None:
        if not isinstance(
            binding,
            TeamsConversationBinding,
        ):
            raise TypeError(
                "binding debe ser "
                "TeamsConversationBinding."
            )

        _require_exact_string(
            name="tenant_id",
            value=binding.tenant_id,
        )

        _require_exact_string(
            name="conversation_id",
            value=binding.conversation_id,
        )

        _require_exact_string(
            name="service_url",
            value=binding.service_url,
        )

    def upsert(
        self,
        binding: TeamsConversationBinding,
    ) -> None:
        self._validate_binding(
            binding
        )

        parameters = {
            "tenant_id": (
                binding.tenant_id
            ),
            "conversation_id": (
                binding.conversation_id
            ),
            "service_url": (
                binding.service_url
            ),
        }

        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                _UPDATE_BINDING,
                parameters,
            )

            if cursor.rowcount == 0:
                cursor.execute(
                    _INSERT_BINDING,
                    parameters,
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()

    def get_exact(
        self,
        *,
        tenant_id: str,
        conversation_id: str,
    ) -> TeamsConversationBinding:
        tenant_id = _require_exact_string(
            name="tenant_id",
            value=tenant_id,
        )

        conversation_id = _require_exact_string(
            name="conversation_id",
            value=conversation_id,
        )

        parameters = {
            "tenant_id": tenant_id,
            "conversation_id": (
                conversation_id
            ),
        }

        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                _GET_EXACT_BINDING,
                parameters,
            )

            row = cursor.fetchone()

        finally:
            if cursor is not None:
                cursor.close()

            connection.close()

        if row is None:
            raise TeamsConversationBindingNotFoundError(
                "No existe binding exacto para "
                "tenant_id y conversation_id."
            )

        stored_tenant_id = _require_exact_string(
            name="stored_tenant_id",
            value=row[0],
        )

        stored_conversation_id = _require_exact_string(
            name="stored_conversation_id",
            value=row[1],
        )

        stored_service_url = _require_exact_string(
            name="stored_service_url",
            value=row[2],
        )

        if (
            stored_tenant_id != tenant_id
            or stored_conversation_id
            != conversation_id
        ):
            raise RuntimeError(
                "El backend devolvio un binding "
                "con identidad distinta."
            )

        return TeamsConversationBinding(
            tenant_id=stored_tenant_id,
            conversation_id=(
                stored_conversation_id
            ),
            service_url=stored_service_url,
        )