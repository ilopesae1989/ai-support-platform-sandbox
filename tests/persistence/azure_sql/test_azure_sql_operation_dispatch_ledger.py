from __future__ import annotations

import importlib
import inspect

from pathlib import Path

import pytest


from src.workflows.incident_resolution.operation_dispatch_ledger import (
    OperationAlreadyDispatchedError,
)


MODULE_NAME = (
    "src.persistence.azure_sql."
    "operation_dispatch_ledger"
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
    / "operation_dispatch_ledger.py"
)


class FakeIntegrityError(
    Exception
):
    pass


class FakeCursor:
    def __init__(
        self,
        *,
        execute_error=None,
        fetchone_result=None,
    ):
        self.execute_error = execute_error
        self.fetchone_result = (
            fetchone_result
        )
        self.executions = []
        self.close_count = 0

    def execute(
        self,
        statement,
        parameters=None,
    ):
        self.executions.append(
            (
                statement,
                parameters,
            )
        )

        if self.execute_error is not None:
            raise self.execute_error

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
    IntegrityError = FakeIntegrityError

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


def _load_adapter_class():
    assert MODULE_PATH.is_file(), (
        "Debe existir el adapter Azure SQL en "
        "src/persistence/azure_sql/"
        "operation_dispatch_ledger.py"
    )

    module = importlib.import_module(
        MODULE_NAME
    )

    adapter = getattr(
        module,
        "AzureSqlOperationDispatchLedger",
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


def test_azure_sql_operation_dispatch_ledger_exists():
    adapter = _load_adapter_class()

    signature = inspect.signature(
        adapter
    )

    assert (
        "connection_factory"
        in signature.parameters
    )


def test_claim_uses_single_parameterized_insert_and_commits():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor()

    connection = FakeConnection(
        cursor=cursor
    )

    ledger = adapter_type(
        connection_factory=(
            lambda: connection
        )
    )

    ledger.claim(
        "operation-001"
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
        "INSERT INTO "
        "DBO.OPERATION_DISPATCH_CLAIMS"
        in normalized
    )

    assert "OPERATION_ID" in normalized

    assert (
        "%(operation_id)s"
        in statement
        or "?" in statement
    )

    assert (
        "operation-001"
        not in statement
    )

    if isinstance(
        parameters,
        dict,
    ):
        assert parameters == {
            "operation_id": (
                "operation-001"
            )
        }

    else:
        assert parameters == (
            "operation-001",
        )

    assert connection.commit_count == 1
    assert connection.rollback_count == 0
    assert connection.close_count == 1
    assert cursor.close_count == 1


def test_duplicate_integrity_error_rolls_back_and_fails_closed():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        execute_error=(
            FakeIntegrityError(
                "duplicate primary key"
            )
        )
    )

    connection = FakeConnection(
        cursor=cursor
    )

    ledger = adapter_type(
        connection_factory=(
            lambda: connection
        )
    )

    with pytest.raises(
        OperationAlreadyDispatchedError
    ):
        ledger.claim(
            "operation-duplicate"
        )

    assert connection.commit_count == 0
    assert connection.rollback_count == 1
    assert connection.close_count == 1
    assert cursor.close_count == 1


def test_unexpected_database_error_rolls_back_and_propagates():
    adapter_type = _load_adapter_class()

    expected_error = RuntimeError(
        "database unavailable"
    )

    cursor = FakeCursor(
        execute_error=expected_error
    )

    connection = FakeConnection(
        cursor=cursor
    )

    ledger = adapter_type(
        connection_factory=(
            lambda: connection
        )
    )

    with pytest.raises(
        RuntimeError,
        match="database unavailable",
    ) as exc_info:
        ledger.claim(
            "operation-error"
        )

    assert (
        exc_info.value
        is expected_error
    )

    assert connection.commit_count == 0
    assert connection.rollback_count == 1
    assert connection.close_count == 1
    assert cursor.close_count == 1


def test_contains_is_exact_parameterized_read_only_lookup():
    adapter_type = _load_adapter_class()

    true_cursor = FakeCursor(
        fetchone_result=(1,)
    )

    false_cursor = FakeCursor(
        fetchone_result=None
    )

    true_connection = FakeConnection(
        cursor=true_cursor
    )

    false_connection = FakeConnection(
        cursor=false_cursor
    )

    connections = iter(
        (
            true_connection,
            false_connection,
        )
    )

    ledger = adapter_type(
        connection_factory=(
            lambda: next(
                connections
            )
        )
    )

    assert (
        ledger.contains(
            "operation-present"
        )
        is True
    )

    assert (
        ledger.contains(
            "operation-absent"
        )
        is False
    )

    for cursor, operation_id in (
        (
            true_cursor,
            "operation-present",
        ),
        (
            false_cursor,
            "operation-absent",
        ),
    ):
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
            "SELECT"
            in normalized
        )

        assert (
            "DBO.OPERATION_DISPATCH_CLAIMS"
            in normalized
        )

        assert (
            "WHERE OPERATION_ID"
            in normalized
        )

        assert operation_id not in statement

        if isinstance(
            parameters,
            dict,
        ):
            assert parameters == {
                "operation_id": (
                    operation_id
                )
            }

        else:
            assert parameters == (
                operation_id,
            )

    assert true_connection.commit_count == 0
    assert true_connection.rollback_count == 0
    assert true_connection.close_count == 1
    assert true_cursor.close_count == 1

    assert false_connection.commit_count == 0
    assert false_connection.rollback_count == 0
    assert false_connection.close_count == 1
    assert false_cursor.close_count == 1


def test_runtime_adapter_contains_no_schema_ddl():
    _load_adapter_class()

    source = MODULE_PATH.read_text(
        encoding="utf-8"
    )

    normalized = _normalize_sql(
        source
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