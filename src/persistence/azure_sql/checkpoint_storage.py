from __future__ import annotations

import asyncio
import json

from collections.abc import (
    Callable,
)

from typing import (
    Any,
)

from agent_framework import (
    WorkflowCheckpoint,
    WorkflowCheckpointException,
)

from agent_framework._workflows._checkpoint_encoding import (
    decode_checkpoint_value,
    encode_checkpoint_value,
)


def _require_exact_nonempty_string(
    value: object,
    *,
    name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} debe ser str."
        )

    if (
        not value
        or not value.strip()
        or value != value.strip()
    ):
        raise ValueError(
            f"{name} debe ser exacto y no vacío."
        )

    return value


class AzureSqlCheckpointStorage:
    """
    CheckpointStorage durable respaldado por Azure SQL.

    El adapter no:
    - descubre configuración;
    - construye connection strings;
    - crea tablas;
    - concede permisos;
    - abre superficies alternativas de persistencia.

    La connection_factory y la allowlist son autoridad
    explícitamente inyectada por el composition root.
    """

    def __init__(
        self,
        *,
        connection_factory: Callable[[], Any],
        allowed_checkpoint_types: list[str] | None = None,
    ) -> None:
        if not callable(
            connection_factory
        ):
            raise TypeError(
                "connection_factory debe ser callable."
            )

        if (
            allowed_checkpoint_types is not None
            and not isinstance(
                allowed_checkpoint_types,
                list,
            )
        ):
            raise TypeError(
                "allowed_checkpoint_types debe ser list[str] o None."
            )

        validated_allowed_types: list[str] = []

        for allowed_type in (
            allowed_checkpoint_types
            or []
        ):
            validated_allowed_types.append(
                _require_exact_nonempty_string(
                    allowed_type,
                    name=(
                        "allowed_checkpoint_type"
                    ),
                )
            )

        self._connection_factory = (
            connection_factory
        )

        self._allowed_types = frozenset(
            validated_allowed_types
        )

    @staticmethod
    def _encode_checkpoint(
        checkpoint: WorkflowCheckpoint,
    ) -> str:
        encoded = encode_checkpoint_value(
            checkpoint.to_dict()
        )

        return json.dumps(
            encoded,
            ensure_ascii=False,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        )

    def _decode_checkpoint(
        self,
        payload_json: str,
    ) -> WorkflowCheckpoint:
        encoded = json.loads(
            payload_json
        )

        decoded = decode_checkpoint_value(encoded, allowed_types=self._allowed_types)

        return WorkflowCheckpoint.from_dict(
            decoded
        )

    @staticmethod
    def _close_quietly(
        resource: object | None,
    ) -> None:
        if resource is None:
            return

        close = getattr(
            resource,
            "close",
            None,
        )

        if not callable(
            close
        ):
            return

        try:
            close()
        except Exception:
            return

    @staticmethod
    def _rollback_quietly(
        connection: object,
    ) -> None:
        rollback = getattr(
            connection,
            "rollback",
            None,
        )

        if not callable(
            rollback
        ):
            return

        try:
            rollback()
        except Exception:
            return

    def _save_sync(
        self,
        *,
        checkpoint_id: str,
        workflow_name: str,
        checkpoint_timestamp: str,
        payload_json: str,
    ) -> str:
        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            parameters = {
                "checkpoint_id": (
                    checkpoint_id
                ),
                "workflow_name": (
                    workflow_name
                ),
                "checkpoint_timestamp": (
                    checkpoint_timestamp
                ),
                "payload_json": (
                    payload_json
                ),
            }

            cursor.execute(
                """
                UPDATE dbo.workflow_checkpoints
                WITH (UPDLOCK, SERIALIZABLE)
                SET
                    workflow_name = %(workflow_name)s,
                    checkpoint_timestamp = %(checkpoint_timestamp)s,
                    payload_json = %(payload_json)s
                WHERE
                    checkpoint_id = %(checkpoint_id)s
                """,
                parameters,
            )

            if cursor.rowcount == 0:
                cursor.execute(
                    """
                    INSERT INTO dbo.workflow_checkpoints
                    (
                        checkpoint_id,
                        workflow_name,
                        checkpoint_timestamp,
                        payload_json
                    )
                    VALUES
                    (
                        %(checkpoint_id)s,
                        %(workflow_name)s,
                        %(checkpoint_timestamp)s,
                        %(payload_json)s
                    )
                    """,
                    parameters,
                )

            connection.commit()

            return checkpoint_id

        except Exception:
            self._rollback_quietly(
                connection
            )
            raise

        finally:
            self._close_quietly(
                cursor
            )

            self._close_quietly(
                connection
            )

    def _load_sync(
        self,
        *,
        checkpoint_id: str,
    ) -> WorkflowCheckpoint:
        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    payload_json
                FROM dbo.workflow_checkpoints
                WHERE
                    checkpoint_id = %(checkpoint_id)s
                """,
                {
                    "checkpoint_id": (
                        checkpoint_id
                    )
                },
            )

            row = cursor.fetchone()

            if row is None:
                raise WorkflowCheckpointException(
                    "No checkpoint found with ID "
                    + checkpoint_id
                )

            return self._decode_checkpoint(
                row[0]
            )

        finally:
            self._close_quietly(
                cursor
            )

            self._close_quietly(
                connection
            )

    def _get_latest_sync(
        self,
        *,
        workflow_name: str,
    ) -> WorkflowCheckpoint | None:
        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT TOP (1)
                    payload_json
                FROM dbo.workflow_checkpoints
                WHERE
                    workflow_name = %(workflow_name)s
                ORDER BY
                    checkpoint_timestamp DESC,
                    checkpoint_id DESC
                """,
                {
                    "workflow_name": (
                        workflow_name
                    )
                },
            )

            row = cursor.fetchone()

            if row is None:
                return None

            return self._decode_checkpoint(
                row[0]
            )

        finally:
            self._close_quietly(
                cursor
            )

            self._close_quietly(
                connection
            )

    def _list_checkpoints_sync(
        self,
        *,
        workflow_name: str,
    ) -> list[WorkflowCheckpoint]:
        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    payload_json
                FROM dbo.workflow_checkpoints
                WHERE
                    workflow_name = %(workflow_name)s
                ORDER BY
                    checkpoint_timestamp ASC,
                    checkpoint_id ASC
                """,
                {
                    "workflow_name": (
                        workflow_name
                    )
                },
            )

            rows = cursor.fetchall()

            return [
                self._decode_checkpoint(
                    row[0]
                )
                for row in rows
            ]

        finally:
            self._close_quietly(
                cursor
            )

            self._close_quietly(
                connection
            )

    def _list_checkpoint_ids_sync(
        self,
        *,
        workflow_name: str,
    ) -> list[str]:
        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    checkpoint_id
                FROM dbo.workflow_checkpoints
                WHERE
                    workflow_name = %(workflow_name)s
                ORDER BY
                    checkpoint_timestamp ASC,
                    checkpoint_id ASC
                """,
                {
                    "workflow_name": (
                        workflow_name
                    )
                },
            )

            rows = cursor.fetchall()

            return [
                row[0]
                for row in rows
            ]

        finally:
            self._close_quietly(
                cursor
            )

            self._close_quietly(
                connection
            )

    def _delete_sync(
        self,
        *,
        checkpoint_id: str,
    ) -> bool:
        connection = (
            self._connection_factory()
        )

        cursor = None

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                DELETE FROM dbo.workflow_checkpoints
                OUTPUT DELETED.checkpoint_id
                WHERE
                    checkpoint_id = %(checkpoint_id)s
                """,
                {
                    "checkpoint_id": (
                        checkpoint_id
                    )
                },
            )

            row = cursor.fetchone()

            connection.commit()

            return row is not None

        except Exception:
            self._rollback_quietly(
                connection
            )
            raise

        finally:
            self._close_quietly(
                cursor
            )

            self._close_quietly(
                connection
            )

    async def save(
        self,
        checkpoint: WorkflowCheckpoint,
    ) -> str:
        if not isinstance(
            checkpoint,
            WorkflowCheckpoint,
        ):
            raise TypeError(
                "checkpoint debe ser WorkflowCheckpoint."
            )

        checkpoint_id = (
            _require_exact_nonempty_string(
                checkpoint.checkpoint_id,
                name="checkpoint_id",
            )
        )

        workflow_name = (
            _require_exact_nonempty_string(
                checkpoint.workflow_name,
                name="workflow_name",
            )
        )

        checkpoint_timestamp = (
            _require_exact_nonempty_string(
                checkpoint.timestamp,
                name="checkpoint_timestamp",
            )
        )

        payload_json = (
            self._encode_checkpoint(
                checkpoint
            )
        )

        return await asyncio.to_thread(
            self._save_sync,
            checkpoint_id=checkpoint_id,
            workflow_name=workflow_name,
            checkpoint_timestamp=(
                checkpoint_timestamp
            ),
            payload_json=payload_json,
        )

    async def load(
        self,
        checkpoint_id: str,
    ) -> WorkflowCheckpoint:
        exact_checkpoint_id = (
            _require_exact_nonempty_string(
                checkpoint_id,
                name="checkpoint_id",
            )
        )

        return await asyncio.to_thread(
            self._load_sync,
            checkpoint_id=(
                exact_checkpoint_id
            ),
        )

    async def get_latest(
        self,
        *,
        workflow_name: str,
    ) -> WorkflowCheckpoint | None:
        exact_workflow_name = (
            _require_exact_nonempty_string(
                workflow_name,
                name="workflow_name",
            )
        )

        return await asyncio.to_thread(
            self._get_latest_sync,
            workflow_name=(
                exact_workflow_name
            ),
        )

    async def list_checkpoints(
        self,
        *,
        workflow_name: str,
    ) -> list[WorkflowCheckpoint]:
        exact_workflow_name = (
            _require_exact_nonempty_string(
                workflow_name,
                name="workflow_name",
            )
        )

        return await asyncio.to_thread(
            self._list_checkpoints_sync,
            workflow_name=(
                exact_workflow_name
            ),
        )

    async def list_checkpoint_ids(
        self,
        *,
        workflow_name: str,
    ) -> list[str]:
        exact_workflow_name = (
            _require_exact_nonempty_string(
                workflow_name,
                name="workflow_name",
            )
        )

        return await asyncio.to_thread(
            self._list_checkpoint_ids_sync,
            workflow_name=(
                exact_workflow_name
            ),
        )

    async def delete(
        self,
        checkpoint_id: str,
    ) -> bool:
        exact_checkpoint_id = (
            _require_exact_nonempty_string(
                checkpoint_id,
                name="checkpoint_id",
            )
        )

        return await asyncio.to_thread(
            self._delete_sync,
            checkpoint_id=(
                exact_checkpoint_id
            ),
        )