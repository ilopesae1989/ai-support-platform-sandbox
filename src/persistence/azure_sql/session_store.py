from __future__ import annotations

import asyncio

from collections.abc import Callable
from typing import Any

from agent_framework import (
    AgentSession,
    SessionStore,
)

from src.runtime.agent_session_snapshot import (
    decode_agent_session_snapshot,
    encode_agent_session_snapshot,
)


_UPDATE_SESSION = """
UPDATE dbo.agent_sessions
WITH (UPDLOCK, SERIALIZABLE)
SET
    payload_json = %(payload_json)s
WHERE
    session_store_id = %(session_store_id)s
"""


_INSERT_SESSION = """
INSERT INTO dbo.agent_sessions (
    session_store_id,
    payload_json
)
VALUES (
    %(session_store_id)s,
    %(payload_json)s
)
"""


_SELECT_SESSION = """
SELECT
    payload_json
FROM
    dbo.agent_sessions
WHERE
    session_store_id = %(session_store_id)s
"""


_DELETE_SESSION = """
DELETE FROM
    dbo.agent_sessions
WHERE
    session_store_id = %(session_store_id)s
"""


def _require_exact_session_store_id(
    value: object,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            "session_store_id debe ser str."
        )

    if (
        not value
        or not value.strip()
        or value != value.strip()
    ):
        raise ValueError(
            "session_store_id debe ser un "
            "string exacto no vacío."
        )

    return value


def _close_quietly(
    resource: object,
) -> None:
    if resource is None:
        return

    close = getattr(
        resource,
        "close",
        None,
    )

    if callable(
        close
    ):
        try:
            close()
        except Exception:
            pass


def _rollback_quietly(
    connection: object,
) -> None:
    if connection is None:
        return

    rollback = getattr(
        connection,
        "rollback",
        None,
    )

    if callable(
        rollback
    ):
        try:
            rollback()
        except Exception:
            pass


class AzureSqlSessionStore(
    SessionStore
):
    def __init__(
        self,
        *,
        connection_factory: Callable[
            [],
            Any,
        ],
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

    def _set_sync(
        self,
        *,
        session_store_id: str,
        payload_json: str,
    ) -> None:
        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            parameters = {
                "session_store_id": (
                    session_store_id
                ),
                "payload_json": (
                    payload_json
                ),
            }

            cursor.execute(
                _UPDATE_SESSION,
                parameters,
            )

            if cursor.rowcount == 0:
                cursor.execute(
                    _INSERT_SESSION,
                    parameters,
                )

            connection.commit()

        except Exception:
            _rollback_quietly(
                connection
            )
            raise

        finally:
            _close_quietly(
                cursor
            )
            _close_quietly(
                connection
            )

    def _get_sync(
        self,
        *,
        session_store_id: str,
    ) -> AgentSession | None:
        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                _SELECT_SESSION,
                {
                    "session_store_id": (
                        session_store_id
                    ),
                },
            )

            row = cursor.fetchone()

            if row is None:
                return None

            payload_json = row[
                0
            ]

            return (
                decode_agent_session_snapshot(
                    payload_json
                )
            )

        finally:
            _close_quietly(
                cursor
            )
            _close_quietly(
                connection
            )

    def _delete_sync(
        self,
        *,
        session_store_id: str,
    ) -> None:
        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                _DELETE_SESSION,
                {
                    "session_store_id": (
                        session_store_id
                    ),
                },
            )

            connection.commit()

        except Exception:
            _rollback_quietly(
                connection
            )
            raise

        finally:
            _close_quietly(
                cursor
            )
            _close_quietly(
                connection
            )

    async def get(
        self,
        session_id: str,
    ) -> AgentSession | None:
        session_store_id = (
            _require_exact_session_store_id(
                session_id
            )
        )

        return await asyncio.to_thread(
            self._get_sync,
            session_store_id=(
                session_store_id
            ),
        )

    async def set(
        self,
        session_id: str,
        session: AgentSession,
    ) -> None:
        session_store_id = (
            _require_exact_session_store_id(
                session_id
            )
        )

        if type(session) is not AgentSession:
            raise TypeError(
                "session debe ser exactamente "
                "AgentSession."
            )

        payload_json = (
            encode_agent_session_snapshot(
                session
            )
        )

        await asyncio.to_thread(
            self._set_sync,
            session_store_id=(
                session_store_id
            ),
            payload_json=(
                payload_json
            ),
        )

    async def delete(
        self,
        session_id: str,
    ) -> None:
        session_store_id = (
            _require_exact_session_store_id(
                session_id
            )
        )

        await asyncio.to_thread(
            self._delete_sync,
            session_store_id=(
                session_store_id
            ),
        )
