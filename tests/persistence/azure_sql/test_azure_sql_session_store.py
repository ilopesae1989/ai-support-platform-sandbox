from __future__ import annotations

import importlib
import inspect
import textwrap

import pytest

from agent_framework import (
    AgentSession,
    SessionStore,
)

from src.runtime.agent_session_snapshot import (
    AgentSessionSnapshotError,
    encode_agent_session_snapshot,
)


MODULE_NAME = (
    "src.persistence.azure_sql.session_store"
)


SESSION_STORE_ID = (
    "cs1:"
    + ("a" * 64)
)


class FakeCursor:
    def __init__(
        self,
        *,
        rowcounts=(),
        fetchone_results=(),
        execute_error_at=None,
        execute_error=None,
    ):
        self._rowcounts = list(
            rowcounts
        )

        self._fetchone_results = list(
            fetchone_results
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


def _module():
    return importlib.import_module(
        MODULE_NAME
    )


def _adapter_type():
    module = _module()

    adapter_type = getattr(
        module,
        "AzureSqlSessionStore",
        None,
    )

    assert inspect.isclass(
        adapter_type
    )

    return adapter_type


def _session(
    *,
    name="Alice",
):
    session = AgentSession(
        session_id="agent-session-001",
        service_session_id=(
            "service-session-001"
        ),
    )

    session.state = {
        "turn": 4,
        "profile": {
            "name": name,
            "locale": "es-ES",
        },
    }

    return session


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


def _assert_closed(
    connection,
    cursor,
):
    assert connection.close_count == 1
    assert cursor.close_count == 1


def test_adapter_is_session_store_with_exact_constructor_surface():
    adapter_type = _adapter_type()

    assert issubclass(
        adapter_type,
        SessionStore,
    )

    signature = inspect.signature(
        adapter_type
    )

    assert tuple(
        signature.parameters
    ) == (
        "connection_factory",
    )

    assert (
        signature.parameters[
            "connection_factory"
        ].kind
        is inspect.Parameter.KEYWORD_ONLY
    )


def test_session_store_protocol_methods_are_async():
    adapter_type = _adapter_type()

    for method_name in (
        "get",
        "set",
        "delete",
    ):
        assert inspect.iscoroutinefunction(
            getattr(
                adapter_type,
                method_name,
            )
        )


def test_constructor_requires_callable_connection_factory():
    adapter_type = _adapter_type()

    for value in (
        None,
        object(),
        123,
        "connection",
    ):
        with pytest.raises(
            TypeError
        ):
            adapter_type(
                connection_factory=value
            )


@pytest.mark.asyncio
async def test_store_id_validation_fails_before_connection():
    adapter_type = _adapter_type()

    factory_calls = 0

    def connection_factory():
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError(
            "connection_factory no debe llamarse"
        )

    store = adapter_type(
        connection_factory=connection_factory
    )

    invalid_ids = (
        None,
        object(),
        "",
        " ",
        " session",
        "session ",
        "\tsession",
        "session\n",
    )

    for invalid in invalid_ids:
        with pytest.raises(
            (
                TypeError,
                ValueError,
            )
        ):
            await store.get(
                invalid
            )

        with pytest.raises(
            (
                TypeError,
                ValueError,
            )
        ):
            await store.delete(
                invalid
            )

        with pytest.raises(
            (
                TypeError,
                ValueError,
            )
        ):
            await store.set(
                invalid,
                _session(),
            )

    assert factory_calls == 0


@pytest.mark.asyncio
async def test_set_rejects_non_agent_session_before_connection():
    adapter_type = _adapter_type()

    factory_calls = 0

    def connection_factory():
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError(
            "connection_factory no debe llamarse"
        )

    store = adapter_type(
        connection_factory=connection_factory
    )

    for value in (
        None,
        object(),
        {},
        "session",
    ):
        with pytest.raises(
            TypeError
        ):
            await store.set(
                SESSION_STORE_ID,
                value,
            )

    assert factory_calls == 0


@pytest.mark.asyncio
async def test_set_existing_session_uses_locked_parameterized_update():
    adapter_type = _adapter_type()

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
        )
    )

    session = _session()

    result = await store.set(
        SESSION_STORE_ID,
        session,
    )

    assert result is None

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
        "DBO.AGENT_SESSIONS "
        "WITH (UPDLOCK, SERIALIZABLE)"
        in normalized
    )

    assert (
        "SET PAYLOAD_JSON = "
        "%(PAYLOAD_JSON)S"
        in normalized
    )

    assert (
        "WHERE SESSION_STORE_ID = "
        "%(SESSION_STORE_ID)S"
        in normalized
    )

    assert parameters[
        "session_store_id"
    ] == SESSION_STORE_ID

    assert parameters[
        "payload_json"
    ] == encode_agent_session_snapshot(
        session
    )

    assert connection.commit_count == 1
    assert connection.rollback_count == 0

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_set_missing_session_updates_then_inserts_without_merge():
    adapter_type = _adapter_type()

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
        )
    )

    result = await store.set(
        SESSION_STORE_ID,
        _session(),
    )

    assert result is None

    assert len(
        cursor.executions
    ) == 2

    first_statement = _normalize_sql(
        cursor.executions[
            0
        ][
            0
        ]
    )

    second_statement = _normalize_sql(
        cursor.executions[
            1
        ][
            0
        ]
    )

    assert first_statement.startswith(
        "UPDATE DBO.AGENT_SESSIONS"
    )

    assert second_statement.startswith(
        "INSERT INTO DBO.AGENT_SESSIONS"
    )

    assert "MERGE " not in first_statement
    assert "MERGE " not in second_statement

    insert_parameters = (
        cursor.executions[
            1
        ][
            1
        ]
    )

    assert insert_parameters[
        "session_store_id"
    ] == SESSION_STORE_ID

    assert isinstance(
        insert_parameters[
            "payload_json"
        ],
        str,
    )

    assert connection.commit_count == 1
    assert connection.rollback_count == 0

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_set_database_failure_rolls_back_closes_and_propagates():
    adapter_type = _adapter_type()

    expected_error = RuntimeError(
        "session SQL failure"
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
        )
    )

    with pytest.raises(
        RuntimeError,
        match="session SQL failure",
    ) as exc_info:
        await store.set(
            SESSION_STORE_ID,
            _session(),
        )

    assert exc_info.value is expected_error

    assert connection.commit_count == 0
    assert connection.rollback_count == 1

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_get_missing_session_returns_none_without_write_transaction():
    adapter_type = _adapter_type()

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
        )
    )

    result = await store.get(
        SESSION_STORE_ID
    )

    assert result is None

    assert len(
        cursor.executions
    ) == 1

    statement, parameters = (
        cursor.executions[
            0
        ]
    )

    normalized = _normalize_sql(
        statement
    )

    assert (
        "SELECT PAYLOAD_JSON "
        "FROM DBO.AGENT_SESSIONS "
        "WHERE SESSION_STORE_ID = "
        "%(SESSION_STORE_ID)S"
        in normalized
    )

    assert parameters == {
        "session_store_id": (
            SESSION_STORE_ID
        )
    }

    assert connection.commit_count == 0
    assert connection.rollback_count == 0

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_get_restores_complete_independent_agent_session():
    adapter_type = _adapter_type()

    original = _session()

    payload = (
        encode_agent_session_snapshot(
            original
        )
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
        )
    )

    restored = await store.get(
        SESSION_STORE_ID
    )

    assert type(
        restored
    ) is AgentSession

    assert restored is not original

    assert (
        restored.session_id
        == original.session_id
    )

    assert (
        restored.service_session_id
        == original.service_session_id
    )

    assert restored.state == original.state

    restored.state[
        "profile"
    ][
        "name"
    ] = "Bob"

    assert original.state[
        "profile"
    ][
        "name"
    ] == "Alice"

    assert connection.commit_count == 0
    assert connection.rollback_count == 0

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_get_corrupt_snapshot_fails_closed_and_closes_resources():
    adapter_type = _adapter_type()

    cursor = FakeCursor(
        fetchone_results=(
            (
                '{"type":"other"}',
            ),
        )
    )

    connection = FakeConnection(
        cursor=cursor
    )

    store = adapter_type(
        connection_factory=(
            lambda: connection
        )
    )

    with pytest.raises(
        AgentSessionSnapshotError
    ):
        await store.get(
            SESSION_STORE_ID
        )

    assert connection.commit_count == 0
    assert connection.rollback_count == 0

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_delete_is_parameterized_idempotent_and_commits():
    adapter_type = _adapter_type()

    cursor = FakeCursor(
        rowcounts=(
            0,
        )
    )

    connection = FakeConnection(
        cursor=cursor
    )

    store = adapter_type(
        connection_factory=(
            lambda: connection
        )
    )

    result = await store.delete(
        SESSION_STORE_ID
    )

    assert result is None

    assert len(
        cursor.executions
    ) == 1

    statement, parameters = (
        cursor.executions[
            0
        ]
    )

    normalized = _normalize_sql(
        statement
    )

    assert (
        "DELETE FROM DBO.AGENT_SESSIONS "
        "WHERE SESSION_STORE_ID = "
        "%(SESSION_STORE_ID)S"
        in normalized
    )

    assert parameters == {
        "session_store_id": (
            SESSION_STORE_ID
        )
    }

    assert connection.commit_count == 1
    assert connection.rollback_count == 0

    _assert_closed(
        connection,
        cursor,
    )


@pytest.mark.asyncio
async def test_delete_database_failure_rolls_back_closes_and_propagates():
    adapter_type = _adapter_type()

    expected_error = RuntimeError(
        "delete SQL failure"
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
        )
    )

    with pytest.raises(
        RuntimeError,
        match="delete SQL failure",
    ) as exc_info:
        await store.delete(
            SESSION_STORE_ID
        )

    assert exc_info.value is expected_error

    assert connection.commit_count == 0
    assert connection.rollback_count == 1

    _assert_closed(
        connection,
        cursor,
    )


def test_adapter_has_no_identity_ddl_or_connection_authority():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.lower()

    required = (
        "sessionstore",
        "encode_agent_session_snapshot",
        "decode_agent_session_snapshot",
        "dbo.agent_sessions",
        "asyncio.to_thread",
        "%(session_store_id)s",
        "%(payload_json)s",
    )

    for fragment in required:
        assert fragment in lowered

    forbidden = (
        "os.environ",
        "os.getenv",
        "managedidentitycredential",
        "defaultazurecredential",
        "azureclicredential",
        "mssql_python.connect",
        "build_mssql_python_connection_factory",
        "create table",
        "alter table",
        "drop table",
        "truncate table",
        "tenant_id",
        "conversation_id",
        "agent_key",
        "service_session_id ==",
        "service_session_id !=",
        "merge ",
        "cosmos",
        "redis",
        "sqlite",
        "teams",
        "foundry",
        "mcp",
    )

    for fragment in forbidden:
        assert fragment not in lowered
