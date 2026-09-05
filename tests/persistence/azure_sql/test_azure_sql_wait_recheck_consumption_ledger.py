from __future__ import annotations

import importlib
import inspect
import re

from pathlib import Path

import pytest

from src.workflows.incident_resolution.wait_recheck_consumption_ledger import (
    WaitRecheckAlreadyConsumedError,
)


MODULE_NAME = (
    "src.persistence.azure_sql."
    "wait_recheck_consumption_ledger"
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
    / "wait_recheck_consumption_ledger.py"
)

MIGRATION_PATH = (
    REPO_ROOT
    / "platform"
    / "azure-sql"
    / "migrations"
    / "004_wait_recheck_consumption.sql"
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
        self.execute_error = (
            execute_error
        )

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


def _load_adapter():
    module = importlib.import_module(
        MODULE_NAME
    )

    adapter = getattr(
        module,
        "AzureSqlWaitRecheckConsumptionLedger",
        None,
    )

    assert inspect.isclass(
        adapter
    )

    return adapter


def _normalize_sql(
    value,
):
    return " ".join(
        str(value)
        .upper()
        .split()
    )


def test_azure_sql_wait_recheck_adapter_exists_as_separate_contract():
    adapter = _load_adapter()

    signature = inspect.signature(
        adapter
    )

    assert (
        "connection_factory"
        in signature.parameters
    )

    module_source = (
        MODULE_PATH.read_text(
            encoding="utf-8"
        )
    )

    assert (
        "OperationDispatchLedger"
        not in module_source
    )

    assert (
        "PendingApprovalStore"
        not in module_source
    )

    assert (
        "IncidentContinuationStore"
        not in module_source
    )


def test_claim_is_single_parameterized_insert_and_commit():
    adapter_type = _load_adapter()

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
        "rchk-azure-sql-001"
    )

    assert len(
        cursor.executions
    ) == 1

    statement, parameters = (
        cursor.executions[0]
    )

    normalized = (
        _normalize_sql(
            statement
        )
    )

    assert (
        "INSERT INTO "
        "DBO.WAIT_RECHECK_CONSUMPTION_CLAIMS"
        in normalized
    )

    assert (
        "RECHECK_ID"
        in normalized
    )

    assert (
        "%(recheck_id)s"
        in statement
        or "?" in statement
    )

    assert (
        "rchk-azure-sql-001"
        not in statement
    )

    if isinstance(
        parameters,
        dict,
    ):
        assert parameters == {
            "recheck_id":
                "rchk-azure-sql-001"
        }

    else:
        assert parameters == (
            "rchk-azure-sql-001",
        )

    assert (
        connection.commit_count
        == 1
    )

    assert (
        connection.rollback_count
        == 0
    )

    assert (
        cursor.close_count
        == 1
    )

    assert (
        connection.close_count
        == 1
    )


def test_duplicate_integrity_error_rolls_back_and_fails_closed():
    adapter_type = _load_adapter()

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
        WaitRecheckAlreadyConsumedError
    ):
        ledger.claim(
            "rchk-duplicate-001"
        )

    assert (
        connection.commit_count
        == 0
    )

    assert (
        connection.rollback_count
        == 1
    )

    assert (
        cursor.close_count
        == 1
    )

    assert (
        connection.close_count
        == 1
    )


def test_contains_is_parameterized_read_only_lookup():
    adapter_type = _load_adapter()

    cursor = FakeCursor(
        fetchone_result=(1,)
    )

    connection = FakeConnection(
        cursor=cursor
    )

    ledger = adapter_type(
        connection_factory=(
            lambda: connection
        )
    )

    assert (
        ledger.contains(
            "rchk-present-001"
        )
        is True
    )

    assert len(
        cursor.executions
    ) == 1

    statement, parameters = (
        cursor.executions[0]
    )

    normalized = (
        _normalize_sql(
            statement
        )
    )

    assert (
        "SELECT"
        in normalized
    )

    assert (
        "DBO.WAIT_RECHECK_CONSUMPTION_CLAIMS"
        in normalized
    )

    assert (
        "WHERE RECHECK_ID"
        in normalized
    )

    assert (
        "rchk-present-001"
        not in statement
    )

    if isinstance(
        parameters,
        dict,
    ):
        assert parameters == {
            "recheck_id":
                "rchk-present-001"
        }

    else:
        assert parameters == (
            "rchk-present-001",
        )

    assert (
        connection.commit_count
        == 0
    )

    assert (
        connection.rollback_count
        == 0
    )

    assert (
        cursor.close_count
        == 1
    )

    assert (
        connection.close_count
        == 1
    )


def test_runtime_adapter_contains_no_schema_or_destructive_ddl():
    _load_adapter()

    source = MODULE_PATH.read_text(
        encoding="utf-8"
    )

    normalized = (
        _normalize_sql(
            source
        )
    )

    forbidden = (
        "CREATE TABLE",
        "ALTER TABLE",
        "DROP TABLE",
        "TRUNCATE TABLE",
        "CREATE DATABASE",
        "DROP DATABASE",
        "DELETE FROM",
    )

    for token in forbidden:
        assert token not in normalized


def test_migration_004_materializes_unique_wait_recheck_consumption_authority():
    assert MIGRATION_PATH.is_file(), (
        "Debe existir "
        "platform/azure-sql/migrations/"
        "004_wait_recheck_consumption.sql"
    )

    text = MIGRATION_PATH.read_text(
        encoding="utf-8"
    )

    normalized = (
        _normalize_sql(
            text
        )
    )

    tables = re.findall(
        r"CREATE TABLE DBO\.([A-Z0-9_]+)",
        normalized,
    )

    assert tables == [
        "WAIT_RECHECK_CONSUMPTION_CLAIMS",
    ]

    pattern = (
        r"CREATE TABLE "
        r"DBO\.WAIT_RECHECK_CONSUMPTION_CLAIMS "
        r"\((.*?)\);"
    )

    match = re.search(
        pattern,
        normalized,
        flags=re.DOTALL,
    )

    assert match is not None

    block = match.group(
        1
    )

    assert re.search(
        r"RECHECK_ID\s+NVARCHAR\(256\)\s+NOT NULL",
        block,
    )

    assert (
        "PRIMARY KEY CLUSTERED (RECHECK_ID)"
        in block
    )

    assert (
        "OPERATION_ID"
        not in block
    )

    assert (
        "APPROVAL_ID"
        not in block
    )

    assert (
        "CONSUMPTION_STATUS"
        not in block
    )

    assert (
        "OBJECT_ID("
        in normalized
    )

    assert (
        "DBO.WAIT_RECHECK_CONSUMPTION_CLAIMS"
        in normalized
    )

    for required in (
        "SET XACT_ABORT ON",
        "BEGIN TRY",
        "BEGIN TRANSACTION",
        "COMMIT TRANSACTION",
        "BEGIN CATCH",
        "@@TRANCOUNT",
        "ROLLBACK TRANSACTION",
        "THROW",
    ):
        assert required in normalized

    forbidden = (
        "DROP TABLE",
        "TRUNCATE TABLE",
        "MERGE ",
        "CREATE USER",
        "ALTER ROLE",
        "CREATE LOGIN",
        "PASSWORD=",
        "PASSWORD =",
        "OPERATION_DISPATCH_CLAIMS",
        "TEAMS_CONVERSATION_BINDINGS",
        "PENDING_APPROVALS",
        "INCIDENT_CONTINUATION_JOBS",
        "WORKFLOW_CHECKPOINTS",
        "AGENT_SESSIONS",
    )

    for token in forbidden:
        assert token not in normalized