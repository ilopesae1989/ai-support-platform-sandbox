from __future__ import annotations

from contextlib import (
    closing,
)

import sqlite3

from pathlib import (
    Path,
)

from typing import (
    Protocol,
)

from .conversation_binding import (
    TeamsConversationBinding,
)


class TeamsConversationBindingNotFoundError(
    LookupError
):
    """
    No existe un binding exacto para el tenant
    y conversation_id solicitados.
    """

    pass


class TeamsConversationBindingStore(
    Protocol
):
    """
    Persistencia de destinos de transporte Teams.

    El store no selecciona destinos y no contiene
    ninguna autoridad operacional.
    """

    def upsert(
        self,
        binding: TeamsConversationBinding,
    ) -> None:
        ...

    def get_exact(
        self,
        *,
        tenant_id: str,
        conversation_id: str,
    ) -> TeamsConversationBinding:
        ...


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
            "exacto no vacío."
        )

    return value


class SqliteTeamsConversationBindingStore:
    """
    Store durable mínimo para bindings Teams.

    Clave exacta:

        tenant_id
        conversation_id

    El service_url puede refrescarse cuando llega
    una actividad autenticada posterior para la
    misma conversación.

    No existe:

        first()
        fallback
        fuzzy lookup
        selección automática de destino
        autoridad operacional
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
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                teams_conversation_bindings (
                    tenant_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    service_url TEXT NOT NULL,
                    PRIMARY KEY (
                        tenant_id,
                        conversation_id
                    )
                )
                """
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

        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO
                    teams_conversation_bindings (
                        tenant_id,
                        conversation_id,
                        service_url
                    )
                VALUES (?, ?, ?)
                ON CONFLICT (
                    tenant_id,
                    conversation_id
                )
                DO UPDATE SET
                    service_url = excluded.service_url
                """,
                (
                    binding.tenant_id,
                    binding.conversation_id,
                    binding.service_url,
                ),
            )

    def get_exact(
        self,
        *,
        tenant_id: str,
        conversation_id: str,
    ) -> TeamsConversationBinding:
        tenant_id = (
            _require_exact_string(
                name="tenant_id",
                value=tenant_id,
            )
        )

        conversation_id = (
            _require_exact_string(
                name="conversation_id",
                value=conversation_id,
            )
        )

        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                """
                SELECT
                    tenant_id,
                    conversation_id,
                    service_url
                FROM
                    teams_conversation_bindings
                WHERE
                    tenant_id = ?
                    AND conversation_id = ?
                """,
                (
                    tenant_id,
                    conversation_id,
                ),
            ).fetchone()

        if row is None:
            raise (
                TeamsConversationBindingNotFoundError(
                    "No existe un binding Teams "
                    "exacto para el destino indicado."
                )
            )

        return TeamsConversationBinding(
            tenant_id=(
                row["tenant_id"]
            ),
            conversation_id=(
                row["conversation_id"]
            ),
            service_url=(
                row["service_url"]
            ),
        )
