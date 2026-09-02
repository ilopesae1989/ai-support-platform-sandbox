from __future__ import annotations

import importlib
import inspect
import json

from datetime import (
    datetime,
    timezone,
)

from decimal import (
    Decimal,
)

from pathlib import (
    Path,
)

import pytest

from agent_framework import (
    WorkflowCheckpoint,
    WorkflowCheckpointException,
)

from agent_framework._workflows._checkpoint_encoding import (
    decode_checkpoint_value,
)

from src.workflows.incident_resolution.checkpoint_storage import (
    incident_checkpoint_allowed_types,
)


MODULE_NAME = (
    "src.persistence.azure_sql."
    "checkpoint_storage"
)


REPO_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)


MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "persistence"
    / "azure_sql"
    / "checkpoint_storage.py"
)


CHECKPOINT_ID = "checkpoint-azure-sql-001"
WORKFLOW_NAME = "incident-resolution"


class FakeCursor:
    def __init__(
        self,
        *,
        rowcounts=(),
        fetchone_results=(),
        fetchall_results=(),
        execute_error_at=None,
        execute_error=None,
    ):
        self._rowcounts = list(
            rowcounts
        )

        self._fetchone_results = list(
            fetchone_results
        )

        self._fetchall_results = list(
            fetchall_results
        )

        self.execute_error_at = (
            execute_error_at
        )

        self.execute_error = (
            execute_error
        )

        self.execute_count = 0
        self.executions = []
        self.rowcount = -1
        self.close_count = 0

    def execute(
        self,
        statement,
        parameters=None,
    ):
        self.execute_count += 1

        self.executions.append(
            (
                statement,
                parameters,
            )
        )

        if (
            self.execute_error_at
            == self.execute_count
        ):
            raise self.execute_error

        index = (
            self.execute_count - 1
        )

        if index < len(
            self._rowcounts
        ):
            self.rowcount = (
                self._rowcounts[
                    index
                ]
            )

        return self

    def fetchone(
        self,
    ):
        if not self._fetchone_results:
            return None

        return self._fetchone_results.pop(
            0
        )

    def fetchall(
        self,
    ):
        if not self._fetchall_results:
            return []

        return self._fetchall_results.pop(
            0
        )

    def close(
        self,
    ):
        self.close_count += 1


class FakeConnection:
    def __init__(
        self,
        *,
        cursor,
    ):
        self._cursor = cursor

        self.commit_count = 0
        self.rollback_count = 0
        self.close_count = 0

    def cursor(
        self,
    ):
        return self._cursor

    def commit(
        self,
    ):
        self.commit_count += 1

    def rollback(
        self,
    ):
        self.rollback_count += 1

    def close(
        self,
    ):
        self.close_count += 1


def _checkpoint(
    *,
    checkpoint_id=CHECKPOINT_ID,
    workflow_name=WORKFLOW_NAME,
    timestamp="2026-09-02T08:00:00+00:00",
    state=None,
):
    if state is None:
        state = {
            "value": 42,
        }

    return WorkflowCheckpoint(
        workflow_name=workflow_name,

        graph_signature_hash=(
            "graph-signature-checkpoint-test"
        ),

        checkpoint_id=checkpoint_id,

        timestamp=timestamp,

        state=state,
    )


def _load_adapter_class():
    assert MODULE_PATH.is_file(), (
        "Debe existir "
        "src/persistence/azure_sql/"
        "checkpoint_storage.py"
    )

    module = importlib.import_module(
        MODULE_NAME
    )

    adapter = getattr(
        module,
        "AzureSqlCheckpointStorage",
        None,
    )

    assert inspect.isclass(
        adapter
    )

    return adapter


def _normalize_sql(
    statement,
):
    return " ".join(
        str(
            statement
        )
        .upper()
        .split()
    )


def _encoded_payload(
    checkpoint,
):
    from agent_framework._workflows._checkpoint_encoding import (
        encode_checkpoint_value,
    )

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


def _assert_closed(
    connection,
    cursor,
):
    assert connection.close_count == 1
    assert cursor.close_count == 1


def test_adapter_exists_with_injected_connection_factory_and_allowlist():
    adapter_type = _load_adapter_class()

    signature = inspect.signature(
        adapter_type
    )

    assert (
        signature.parameters[
            "connection_factory"
        ].kind
        is inspect.Parameter.KEYWORD_ONLY
    )

    assert (
        signature.parameters[
            "allowed_checkpoint_types"
        ].kind
        is inspect.Parameter.KEYWORD_ONLY
    )

    assert (
        signature.parameters[
            "allowed_checkpoint_types"
        ].default
        is None
    )


def test_all_checkpoint_protocol_methods_are_async():
    adapter_type = _load_adapter_class()

    for method_name in (
        "save",
        "load",
        "get_latest",
        "list_checkpoints",
        "list_checkpoint_ids",
        "delete",
    ):
        assert inspect.iscoroutinefunction(
            getattr(
                adapter_type,
                method_name,
            )
        )


def test_constructor_freezes_explicit_allowed_checkpoint_types():
    adapter_type = _load_adapter_class()

    allowed = sorted(
        incident_checkpoint_allowed_types()
    )

    store = adapter_type(
        connection_factory=(
            lambda: None
        ),
        allowed_checkpoint_types=allowed,
    )

    assert isinstance(
        store._allowed_types,
        frozenset,
    )

    assert (
        store._allowed_types
        == frozenset(
            allowed
        )
    )


@pytest.mark.asyncio
async def test_save_existing_checkpoint_uses_locked_parameterized_update():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        rowcounts=(
            1,
        )
    )

    connection = FakeConnection(
        cursor=cursor
    )

    store = adapter_type(
        connection_factory=(
            lambda: connection
        ),
        allowed_checkpoint_types=sorted(
            incident_checkpoint_allowed_types()
        ),
    )

    checkpoint = _checkpoint()

    result = await store.save(
        checkpoint
    )

    assert result == CHECKPOINT_ID

    assert len(
        cursor.executions
    ) == 1

    statement, parameters = (
        cursor.executions[0]
    )

    normalized = _normalize_sql(
        statement
    )

    assert (
        "UPDATE "
        "DBO.WORKFLOW_CHECKPOINTS "
        "WITH (UPDLOCK, SERIALIZABLE)"
        in normalized
    )

    assert (
        "WHERE CHECKPOINT_ID = "
        "%(CHECKPOINT_ID)S"
        in normalized
    )

    assert parameters[
        "checkpoint_id"
    ] == CHECKPOINT_ID

    assert parameters[
        "workflow_name"
    ] == WORKFLOW_NAME

    assert parameters[
        "checkpoint_timestamp"
    ] == checkpoint.timestamp

    json.loads(
        parameters[
            "payload_json"
        ]
    )

    assert connection.commit_count == 1
    assert connection.rollback_count == 0

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_save_missing_checkpoint_updates_then_inserts_without_merge():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        rowcounts=(
            0,
            1,
        )
    )

    connection = FakeConnection(
        cursor=cursor
    )

    store = adapter_type(
        connection_factory=(
            lambda: connection
        ),
    )

    result = await store.save(
        _checkpoint()
    )

    assert result == CHECKPOINT_ID

    assert len(
        cursor.executions
    ) == 2

    first = _normalize_sql(
        cursor.executions[
            0
        ][
            0
        ]
    )

    second = _normalize_sql(
        cursor.executions[
            1
        ][
            0
        ]
    )

    assert first.startswith(
        "UPDATE "
        "DBO.WORKFLOW_CHECKPOINTS"
    )

    assert second.startswith(
        "INSERT INTO "
        "DBO.WORKFLOW_CHECKPOINTS"
    )

    assert "MERGE " not in first
    assert "MERGE " not in second

    assert connection.commit_count == 1
    assert connection.rollback_count == 0

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_save_database_failure_rolls_back_and_propagates():
    adapter_type = _load_adapter_class()

    expected_error = RuntimeError(
        "checkpoint SQL failure"
    )

    cursor = FakeCursor(
        execute_error_at=1,
        execute_error=expected_error,
    )

    connection = FakeConnection(
        cursor=cursor
    )

    store = adapter_type(
        connection_factory=(
            lambda: connection
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="checkpoint SQL failure",
    ) as exc_info:
        await store.save(
            _checkpoint()
        )

    assert (
        exc_info.value
        is expected_error
    )

    assert connection.commit_count == 0
    assert connection.rollback_count == 1

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_save_payload_roundtrips_framework_restricted_encoding():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        rowcounts=(
            1,
        )
    )

    connection = FakeConnection(
        cursor=cursor
    )

    allowed = sorted(
        incident_checkpoint_allowed_types()
    )

    store = adapter_type(
        connection_factory=(
            lambda: connection
        ),
        allowed_checkpoint_types=allowed,
    )

    checkpoint = _checkpoint(
        state={
            "decimal": Decimal(
                "123.45"
            ),
            "when": datetime(
                2026,
                9,
                2,
                8,
                15,
                0,
                tzinfo=timezone.utc,
            ),
        }
    )

    await store.save(
        checkpoint
    )

    payload_json = (
        cursor.executions[
            0
        ][
            1
        ][
            "payload_json"
        ]
    )

    encoded = json.loads(
        payload_json
    )

    decoded = decode_checkpoint_value(
        encoded,
        allowed_types=frozenset(
            allowed
        ),
    )

    restored = (
        WorkflowCheckpoint
        .from_dict(
            decoded
        )
    )

    assert (
        restored.state[
            "decimal"
        ]
        == Decimal(
            "123.45"
        )
    )

    assert isinstance(
        restored.state[
            "decimal"
        ],
        Decimal,
    )

    assert isinstance(
        restored.state[
            "when"
        ],
        datetime,
    )


@pytest.mark.asyncio
async def test_load_uses_exact_parameterized_lookup_and_restricted_decoder():
    adapter_type = _load_adapter_class()

    checkpoint = _checkpoint()

    payload = _encoded_payload(
        checkpoint
    )

    cursor = FakeCursor(
        fetchone_results=(
            (
                payload,
            ),
        )
    )

    connection = FakeConnection(
        cursor=cursor
    )

    store = adapter_type(
        connection_factory=(
            lambda: connection
        ),
        allowed_checkpoint_types=sorted(
            incident_checkpoint_allowed_types()
        ),
    )

    restored = await store.load(
        CHECKPOINT_ID
    )

    assert (
        restored.checkpoint_id
        == CHECKPOINT_ID
    )

    assert (
        restored.workflow_name
        == WORKFLOW_NAME
    )

    statement, parameters = (
        cursor.executions[
            0
        ]
    )

    normalized = _normalize_sql(
        statement
    )

    assert (
        "FROM DBO.WORKFLOW_CHECKPOINTS"
        in normalized
    )

    assert (
        "WHERE CHECKPOINT_ID = "
        "%(CHECKPOINT_ID)S"
        in normalized
    )

    assert parameters == {
        "checkpoint_id": CHECKPOINT_ID
    }

    assert connection.commit_count == 0
    assert connection.rollback_count == 0

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_load_missing_checkpoint_raises_workflow_checkpoint_exception():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        fetchone_results=(
            None,
        )
    )

    connection = FakeConnection(
        cursor=cursor
    )

    store = adapter_type(
        connection_factory=(
            lambda: connection
        ),
    )

    with pytest.raises(
        WorkflowCheckpointException,
        match="No checkpoint found",
    ):
        await store.load(
            CHECKPOINT_ID
        )

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_get_latest_uses_timestamp_descending_and_checkpoint_tiebreaker():
    adapter_type = _load_adapter_class()

    checkpoint = _checkpoint()

    cursor = FakeCursor(
        fetchone_results=(
            (
                _encoded_payload(
                    checkpoint
                ),
            ),
        )
    )

    connection = FakeConnection(
        cursor=cursor
    )

    store = adapter_type(
        connection_factory=(
            lambda: connection
        ),
    )

    latest = await store.get_latest(
        workflow_name=WORKFLOW_NAME
    )

    assert latest is not None

    assert (
        latest.checkpoint_id
        == CHECKPOINT_ID
    )

    statement, parameters = (
        cursor.executions[
            0
        ]
    )

    normalized = _normalize_sql(
        statement
    )

    assert "SELECT TOP (1)" in normalized

    assert (
        "WHERE WORKFLOW_NAME = "
        "%(WORKFLOW_NAME)S"
        in normalized
    )

    assert (
        "ORDER BY "
        "CHECKPOINT_TIMESTAMP DESC, "
        "CHECKPOINT_ID DESC"
        in normalized
    )

    assert parameters == {
        "workflow_name": WORKFLOW_NAME
    }

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_get_latest_returns_none_when_workflow_has_no_checkpoints():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        fetchone_results=(
            None,
        )
    )

    connection = FakeConnection(
        cursor=cursor
    )

    store = adapter_type(
        connection_factory=(
            lambda: connection
        ),
    )

    result = await store.get_latest(
        workflow_name=WORKFLOW_NAME
    )

    assert result is None

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_list_checkpoints_returns_decoded_deterministic_order():
    adapter_type = _load_adapter_class()

    first = _checkpoint(
        checkpoint_id=(
            "checkpoint-001"
        ),
        timestamp=(
            "2026-09-02T08:00:00+00:00"
        ),
    )

    second = _checkpoint(
        checkpoint_id=(
            "checkpoint-002"
        ),
        timestamp=(
            "2026-09-02T08:01:00+00:00"
        ),
    )

    cursor = FakeCursor(
        fetchall_results=(
            [
                (
                    _encoded_payload(
                        first
                    ),
                ),
                (
                    _encoded_payload(
                        second
                    ),
                ),
            ],
        )
    )

    connection = FakeConnection(
        cursor=cursor
    )

    store = adapter_type(
        connection_factory=(
            lambda: connection
        ),
    )

    result = (
        await store.list_checkpoints(
            workflow_name=WORKFLOW_NAME
        )
    )

    assert [
        checkpoint.checkpoint_id
        for checkpoint in result
    ] == [
        "checkpoint-001",
        "checkpoint-002",
    ]

    normalized = _normalize_sql(
        cursor.executions[
            0
        ][
            0
        ]
    )

    assert (
        "ORDER BY "
        "CHECKPOINT_TIMESTAMP ASC, "
        "CHECKPOINT_ID ASC"
        in normalized
    )

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_list_checkpoint_ids_does_not_deserialize_payloads():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        fetchall_results=(
            [
                (
                    "checkpoint-001",
                ),
                (
                    "checkpoint-002",
                ),
            ],
        )
    )

    connection = FakeConnection(
        cursor=cursor
    )

    store = adapter_type(
        connection_factory=(
            lambda: connection
        ),
    )

    result = (
        await store.list_checkpoint_ids(
            workflow_name=WORKFLOW_NAME
        )
    )

    assert result == [
        "checkpoint-001",
        "checkpoint-002",
    ]

    normalized = _normalize_sql(
        cursor.executions[
            0
        ][
            0
        ]
    )

    assert (
        "SELECT CHECKPOINT_ID"
        in normalized
    )

    assert (
        "PAYLOAD_JSON"
        not in normalized
    )

    assert (
        "ORDER BY "
        "CHECKPOINT_TIMESTAMP ASC, "
        "CHECKPOINT_ID ASC"
        in normalized
    )

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_delete_existing_checkpoint_uses_output_and_returns_true():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        fetchone_results=(
            (
                CHECKPOINT_ID,
            ),
        )
    )

    connection = FakeConnection(
        cursor=cursor
    )

    store = adapter_type(
        connection_factory=(
            lambda: connection
        ),
    )

    deleted = await store.delete(
        CHECKPOINT_ID
    )

    assert deleted is True

    normalized = _normalize_sql(
        cursor.executions[
            0
        ][
            0
        ]
    )

    assert (
        "DELETE FROM "
        "DBO.WORKFLOW_CHECKPOINTS"
        in normalized
    )

    assert (
        "OUTPUT DELETED.CHECKPOINT_ID"
        in normalized
    )

    assert (
        "WHERE CHECKPOINT_ID = "
        "%(CHECKPOINT_ID)S"
        in normalized
    )

    assert connection.commit_count == 1
    assert connection.rollback_count == 0

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_delete_missing_checkpoint_returns_false():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        fetchone_results=(
            None,
        )
    )

    connection = FakeConnection(
        cursor=cursor
    )

    store = adapter_type(
        connection_factory=(
            lambda: connection
        ),
    )

    deleted = await store.delete(
        CHECKPOINT_ID
    )

    assert deleted is False

    assert connection.commit_count == 1
    assert connection.rollback_count == 0

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_invalid_inputs_fail_before_connection_creation():
    adapter_type = _load_adapter_class()

    factory_calls = 0

    def forbidden_factory():
        nonlocal factory_calls

        factory_calls += 1

        raise AssertionError(
            "No debe abrir conexion."
        )

    store = adapter_type(
        connection_factory=(
            forbidden_factory
        ),
    )

    with pytest.raises(
        TypeError
    ):
        await store.save(
            object()
        )

    with pytest.raises(
        ValueError
    ):
        await store.load(
            ""
        )

    with pytest.raises(
        ValueError
    ):
        await store.load(
            " bad "
        )

    with pytest.raises(
        ValueError
    ):
        await store.get_latest(
            workflow_name=" "
        )

    with pytest.raises(
        ValueError
    ):
        await store.list_checkpoints(
            workflow_name=""
        )

    with pytest.raises(
        ValueError
    ):
        await store.list_checkpoint_ids(
            workflow_name=" bad "
        )

    with pytest.raises(
        ValueError
    ):
        await store.delete(
            ""
        )

    assert factory_calls == 0


def test_source_uses_framework_encoder_decoder_and_restricted_allowlist():
    _load_adapter_class()

    source = MODULE_PATH.read_text(
        encoding="utf-8"
    )

    lower_source = source.lower()

    assert (
        "encode_checkpoint_value"
        in source
    )

    assert (
        "decode_checkpoint_value"
        in source
    )

    assert (
        "allowed_types=self._allowed_types"
        in source
    )

    assert (
        "frozenset("
        in source
    )

    forbidden = (
        "pickle.loads",
        "pickle.load(",
        "allowed_types=none",
        "jsonpickle",
        "cloudpickle",
        "dill.loads",
    )

    for token in forbidden:
        assert token not in lower_source


def test_source_contains_no_runtime_ddl_merge_cosmos_or_environment_authority():
    _load_adapter_class()

    source = MODULE_PATH.read_text(
        encoding="utf-8"
    )

    normalized = _normalize_sql(
        source
    )

    lower_source = source.lower()

    for forbidden in (
        "CREATE TABLE",
        "ALTER TABLE",
        "DROP TABLE",
        "MERGE ",
        "TRUNCATE TABLE",
        "CREATE DATABASE",
        "CREATE USER",
        "ALTER ROLE",
    ):
        assert forbidden not in normalized

    for forbidden in (
        "cosmos",
        "filecheckpointstorage",
        "sqlite3",
        "os.getenv",
        "os.environ",
        "azure_sql_connection_string",
        "sql_connection_string",
    ):
        assert forbidden not in lower_source


def test_source_is_sql_only_async_wrapper_and_uses_injected_connection():
    adapter_type = _load_adapter_class()

    source = MODULE_PATH.read_text(
        encoding="utf-8"
    )

    assert (
        "asyncio.to_thread"
        in source
    )

    assert (
        "dbo.workflow_checkpoints"
        in source.lower()
    )

    assert (
        "%(checkpoint_id)s"
        in source.lower()
    )

    assert (
        "%(workflow_name)s"
        in source.lower()
    )

    assert (
        "UPDLOCK"
        in source
    )

    assert (
        "SERIALIZABLE"
        in source
    )

    signature = inspect.signature(
        adapter_type
    )

    assert (
        "connection_factory"
        in signature.parameters
    )

    assert (
        "connection_string"
        not in signature.parameters
    )


def test_protocol_contract_matches_agent_framework_1_13_surface():
    adapter_type = _load_adapter_class()

    expected = (
        "save",
        "load",
        "get_latest",
        "list_checkpoints",
        "list_checkpoint_ids",
        "delete",
    )

    for method_name in expected:
        method = getattr(
            adapter_type,
            method_name,
        )

        assert inspect.iscoroutinefunction(
            method
        )