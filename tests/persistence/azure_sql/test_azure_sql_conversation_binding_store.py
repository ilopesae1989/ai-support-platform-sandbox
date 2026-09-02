from __future__ import annotations

import importlib
import inspect

from pathlib import Path

import pytest


from src.channels.teams.conversation_binding import (
    TeamsConversationBinding,
)

from src.channels.teams.conversation_binding_store import (
    TeamsConversationBindingNotFoundError,
)


MODULE_NAME = (
    "src.persistence.azure_sql."
    "conversation_binding_store"
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
    / "conversation_binding_store.py"
)


TENANT_ID = (
    "3048dc87-43f0-4100-"
    "9acb-ae1971c79395"
)

CONVERSATION_ID = (
    "19:test-conversation@thread.v2"
)

SERVICE_URL = (
    "https://smba.trafficmanager.net/emea/"
)


class FakeCursor:
    def __init__(
        self,
        *,
        rowcounts=(),
        fetchone_result=None,
        execute_error_at=None,
        execute_error=None,
    ):
        self._rowcounts = list(
            rowcounts
        )

        self.fetchone_result = (
            fetchone_result
        )

        self.execute_error_at = (
            execute_error_at
        )

        self.execute_error = (
            execute_error
        )

        self.executions = []

        self.execute_count = 0

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

        if (
            self.execute_count
            <= len(
                self._rowcounts
            )
        ):
            self.rowcount = (
                self._rowcounts[
                    self.execute_count - 1
                ]
            )

        return self

    def fetchone(
        self,
    ):
        return self.fetchone_result

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


def _binding(
    *,
    tenant_id=TENANT_ID,
    conversation_id=CONVERSATION_ID,
    service_url=SERVICE_URL,
):
    return TeamsConversationBinding(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        service_url=service_url,
    )


def _load_adapter_class():
    assert MODULE_PATH.is_file(), (
        "Debe existir "
        "src/persistence/azure_sql/"
        "conversation_binding_store.py"
    )

    module = importlib.import_module(
        MODULE_NAME
    )

    adapter = getattr(
        module,
        "AzureSqlTeamsConversationBindingStore",
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
        str(statement)
        .upper()
        .split()
    )


def _assert_transport_parameters(
    parameters,
    *,
    include_service_url,
):
    assert isinstance(
        parameters,
        dict,
    )

    expected = {
        "tenant_id": TENANT_ID,
        "conversation_id": (
            CONVERSATION_ID
        ),
    }

    if include_service_url:
        expected[
            "service_url"
        ] = SERVICE_URL

    assert parameters == expected


def test_azure_sql_conversation_binding_store_exists():
    adapter = _load_adapter_class()

    signature = inspect.signature(
        adapter
    )

    assert (
        "connection_factory"
        in signature.parameters
    )

    parameter = (
        signature.parameters[
            "connection_factory"
        ]
    )

    assert (
        parameter.kind
        is inspect.Parameter.KEYWORD_ONLY
    )


def test_upsert_existing_binding_uses_locked_parameterized_update_and_commits():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        rowcounts=(1,)
    )

    connection = FakeConnection(
        cursor=cursor
    )

    store = adapter_type(
        connection_factory=(
            lambda: connection
        )
    )

    store.upsert(
        _binding()
    )

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
        "DBO.TEAMS_CONVERSATION_BINDINGS "
        "WITH (UPDLOCK, SERIALIZABLE)"
        in normalized
    )

    assert (
        "SET SERVICE_URL = %(SERVICE_URL)S"
        in normalized
    )

    assert (
        "WHERE TENANT_ID = %(TENANT_ID)S "
        "AND CONVERSATION_ID = %(CONVERSATION_ID)S"
        in normalized
    )

    assert TENANT_ID not in statement
    assert CONVERSATION_ID not in statement
    assert SERVICE_URL not in statement

    _assert_transport_parameters(
        parameters,
        include_service_url=True,
    )

    assert connection.commit_count == 1
    assert connection.rollback_count == 0
    assert connection.close_count == 1
    assert cursor.close_count == 1


def test_upsert_missing_binding_updates_then_inserts_in_same_transaction():
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
        )
    )

    store.upsert(
        _binding()
    )

    assert len(
        cursor.executions
    ) == 2

    update_statement, update_parameters = (
        cursor.executions[0]
    )

    insert_statement, insert_parameters = (
        cursor.executions[1]
    )

    update_normalized = _normalize_sql(
        update_statement
    )

    insert_normalized = _normalize_sql(
        insert_statement
    )

    assert (
        "WITH (UPDLOCK, SERIALIZABLE)"
        in update_normalized
    )

    assert (
        "INSERT INTO "
        "DBO.TEAMS_CONVERSATION_BINDINGS"
        in insert_normalized
    )

    assert (
        "TENANT_ID"
        in insert_normalized
    )

    assert (
        "CONVERSATION_ID"
        in insert_normalized
    )

    assert (
        "SERVICE_URL"
        in insert_normalized
    )

    _assert_transport_parameters(
        update_parameters,
        include_service_url=True,
    )

    _assert_transport_parameters(
        insert_parameters,
        include_service_url=True,
    )

    assert connection.commit_count == 1
    assert connection.rollback_count == 0
    assert connection.close_count == 1
    assert cursor.close_count == 1


def test_upsert_database_error_rolls_back_and_propagates():
    adapter_type = _load_adapter_class()

    expected_error = RuntimeError(
        "write failed"
    )

    cursor = FakeCursor(
        rowcounts=(0,),
        execute_error_at=2,
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
        match="write failed",
    ) as exc_info:
        store.upsert(
            _binding()
        )

    assert (
        exc_info.value
        is expected_error
    )

    assert connection.commit_count == 0
    assert connection.rollback_count == 1
    assert connection.close_count == 1
    assert cursor.close_count == 1


def test_get_exact_returns_typed_binding_from_parameterized_lookup():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        fetchone_result=(
            TENANT_ID,
            CONVERSATION_ID,
            SERVICE_URL,
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

    binding = store.get_exact(
        tenant_id=TENANT_ID,
        conversation_id=(
            CONVERSATION_ID
        ),
    )

    assert binding == _binding()

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
        "SELECT "
        "TENANT_ID, "
        "CONVERSATION_ID, "
        "SERVICE_URL "
        "FROM "
        "DBO.TEAMS_CONVERSATION_BINDINGS"
        in normalized
    )

    assert (
        "WHERE TENANT_ID = %(TENANT_ID)S "
        "AND CONVERSATION_ID = %(CONVERSATION_ID)S"
        in normalized
    )

    _assert_transport_parameters(
        parameters,
        include_service_url=False,
    )

    assert connection.commit_count == 0
    assert connection.rollback_count == 0
    assert connection.close_count == 1
    assert cursor.close_count == 1


def test_get_exact_missing_binding_fails_closed_without_write():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        fetchone_result=None
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
        TeamsConversationBindingNotFoundError
    ):
        store.get_exact(
            tenant_id=TENANT_ID,
            conversation_id=(
                CONVERSATION_ID
            ),
        )

    assert connection.commit_count == 0
    assert connection.rollback_count == 0
    assert connection.close_count == 1
    assert cursor.close_count == 1


def test_adapter_revalidates_transport_boundary_before_connecting():
    adapter_type = _load_adapter_class()

    factory_calls = 0

    def forbidden_factory():
        nonlocal factory_calls

        factory_calls += 1

        raise AssertionError(
            "No debe conectar con input invalido."
        )

    store = adapter_type(
        connection_factory=(
            forbidden_factory
        )
    )

    with pytest.raises(
        TypeError
    ):
        store.upsert(
            object()
        )

    with pytest.raises(
        ValueError
    ):
        store.upsert(
            _binding(
                tenant_id=" bad"
            )
        )

    with pytest.raises(
        ValueError
    ):
        store.upsert(
            _binding(
                service_url=" "
            )
        )

    with pytest.raises(
        ValueError
    ):
        store.get_exact(
            tenant_id="",
            conversation_id=(
                CONVERSATION_ID
            ),
        )

    with pytest.raises(
        ValueError
    ):
        store.get_exact(
            tenant_id=TENANT_ID,
            conversation_id=" bad ",
        )

    assert factory_calls == 0


def test_runtime_adapter_uses_no_merge_no_schema_ddl_and_no_direct_driver_import():
    _load_adapter_class()

    source = MODULE_PATH.read_text(
        encoding="utf-8"
    )

    normalized = _normalize_sql(
        source
    )

    assert " MERGE " not in (
        " " + normalized + " "
    )

    forbidden = (
        "CREATE TABLE",
        "ALTER TABLE",
        "DROP TABLE",
        "CREATE DATABASE",
        "DROP DATABASE",
    )

    for statement in forbidden:
        assert statement not in normalized

    assert "UPDLOCK" in normalized
    assert "SERIALIZABLE" in normalized

    lower_source = source.lower()

    assert (
        "import mssql_python"
        not in lower_source
    )

    assert (
        "from mssql_python"
        not in lower_source
    )