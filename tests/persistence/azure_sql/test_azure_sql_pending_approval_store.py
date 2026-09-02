from __future__ import annotations

import importlib
import inspect

from pathlib import Path

import pytest


from src.runtime.procedure.approval_correlation import (
    ApprovalCorrelationNotFoundError,
    DuplicateApprovalCorrelationError,
    PendingApprovalCorrelation,
)

from src.runtime.procedure.approval_store import (
    ApprovalAlreadyConsumedError,
)


MODULE_NAME = (
    "src.persistence.azure_sql."
    "pending_approval_store"
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
    / "pending_approval_store.py"
)


APPROVAL_ID = (
    "apr-11111111-1111-4111-"
    "8111-111111111111"
)

WORKFLOW_ID = (
    "wf-11111111-1111-4111-"
    "8111-111111111111"
)

REQUEST_ID = (
    "req-agent-framework-001"
)

CHECKPOINT_ID = (
    "checkpoint-hitl-001"
)


CORRELATION_ROW = (
    APPROVAL_ID,
    WORKFLOW_ID,
    REQUEST_ID,
    CHECKPOINT_ID,
)


class FakeIntegrityError(
    Exception
):
    pass


class FakeCursor:
    def __init__(
        self,
        *,
        fetchone_results=(),
        execute_error_at=None,
        execute_error=None,
    ):
        self._fetchone_results = list(
            fetchone_results
        )

        self.execute_error_at = (
            execute_error_at
        )

        self.execute_error = (
            execute_error
        )

        self.executions = []

        self.execute_count = 0

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


def _correlation(
    *,
    approval_id=APPROVAL_ID,
    workflow_id=WORKFLOW_ID,
    request_id=REQUEST_ID,
    checkpoint_id=CHECKPOINT_ID,
):
    return PendingApprovalCorrelation(
        approval_id=approval_id,
        workflow_id=workflow_id,
        request_id=request_id,
        checkpoint_id=checkpoint_id,
    )


def _load_adapter_class():
    assert MODULE_PATH.is_file(), (
        "Debe existir "
        "src/persistence/azure_sql/"
        "pending_approval_store.py"
    )

    module = importlib.import_module(
        MODULE_NAME
    )

    adapter = getattr(
        module,
        "AzureSqlPendingApprovalStore",
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


def _assert_connection_closed(
    connection,
    cursor,
):
    assert connection.close_count == 1
    assert cursor.close_count == 1


def _assert_correlation_parameters(
    parameters,
):
    assert parameters == {
        "approval_id": APPROVAL_ID,
        "workflow_id": WORKFLOW_ID,
        "request_id": REQUEST_ID,
        "checkpoint_id": CHECKPOINT_ID,
    }


def test_azure_sql_pending_approval_store_exists():
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


def test_register_uses_single_parameterized_insert_and_commits():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor()

    connection = FakeConnection(
        cursor=cursor
    )

    store = adapter_type(
        connection_factory=(
            lambda: connection
        )
    )

    store.register(
        _correlation()
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
        "DBO.PENDING_APPROVALS"
        in normalized
    )

    for column in (
        "APPROVAL_ID",
        "WORKFLOW_ID",
        "REQUEST_ID",
        "CHECKPOINT_ID",
    ):
        assert column in normalized

    assert "%(approval_id)s" in statement
    assert "%(workflow_id)s" in statement
    assert "%(request_id)s" in statement
    assert "%(checkpoint_id)s" in statement

    assert APPROVAL_ID not in statement
    assert WORKFLOW_ID not in statement
    assert REQUEST_ID not in statement
    assert CHECKPOINT_ID not in statement

    _assert_correlation_parameters(
        parameters
    )

    assert connection.commit_count == 1
    assert connection.rollback_count == 0

    _assert_connection_closed(
        connection,
        cursor,
    )


def test_register_duplicate_integrity_error_rolls_back_and_maps_domain_error():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        execute_error_at=1,
        execute_error=(
            FakeIntegrityError(
                "duplicate unique key"
            )
        ),
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
        DuplicateApprovalCorrelationError
    ):
        store.register(
            _correlation()
        )

    assert connection.commit_count == 0
    assert connection.rollback_count == 1

    _assert_connection_closed(
        connection,
        cursor,
    )


def test_get_by_approval_id_is_exact_parameterized_lookup():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        fetchone_results=(
            CORRELATION_ROW,
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

    restored = (
        store.get_by_approval_id(
            APPROVAL_ID
        )
    )

    assert restored == _correlation()

    assert set(
        restored.model_dump()
    ) == {
        "approval_id",
        "workflow_id",
        "request_id",
        "checkpoint_id",
    }

    assert len(
        cursor.executions
    ) == 1

    statement, parameters = (
        cursor.executions[0]
    )

    normalized = _normalize_sql(
        statement
    )

    assert "SELECT" in normalized
    assert "DBO.PENDING_APPROVALS" in normalized

    assert (
        "WHERE APPROVAL_ID = %(APPROVAL_ID)S"
        in normalized
    )

    assert parameters == {
        "approval_id": APPROVAL_ID
    }

    assert connection.commit_count == 0
    assert connection.rollback_count == 0

    _assert_connection_closed(
        connection,
        cursor,
    )


def test_get_by_request_id_is_exact_parameterized_lookup():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        fetchone_results=(
            CORRELATION_ROW,
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

    restored = (
        store.get_by_request_id(
            REQUEST_ID
        )
    )

    assert restored == _correlation()

    statement, parameters = (
        cursor.executions[0]
    )

    normalized = _normalize_sql(
        statement
    )

    assert (
        "WHERE REQUEST_ID = %(REQUEST_ID)S"
        in normalized
    )

    assert parameters == {
        "request_id": REQUEST_ID
    }

    assert connection.commit_count == 0
    assert connection.rollback_count == 0

    _assert_connection_closed(
        connection,
        cursor,
    )


def test_missing_lookup_fails_closed_without_write():
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
        )
    )

    with pytest.raises(
        ApprovalCorrelationNotFoundError
    ):
        store.get_by_approval_id(
            APPROVAL_ID
        )

    assert connection.commit_count == 0
    assert connection.rollback_count == 0

    _assert_connection_closed(
        connection,
        cursor,
    )


def test_claim_is_single_conditional_update_with_output_and_preserves_decision():
    adapter_type = _load_adapter_class()

    for approved, expected_value in (
        (
            True,
            1,
        ),
        (
            False,
            0,
        ),
    ):
        cursor = FakeCursor(
            fetchone_results=(
                CORRELATION_ROW,
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

        claimed = store.claim(
            approval_id=APPROVAL_ID,
            approved=approved,
        )

        assert claimed == _correlation()

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
            "UPDATE DBO.PENDING_APPROVALS"
            in normalized
        )

        assert (
            "CONSUMPTION_STATUS = 'CLAIMED'"
            in normalized
        )

        assert (
            "APPROVED_DECISION = "
            "%(APPROVED_DECISION)S"
            in normalized
        )

        assert "OUTPUT" in normalized
        assert "INSERTED.APPROVAL_ID" in normalized
        assert "INSERTED.WORKFLOW_ID" in normalized
        assert "INSERTED.REQUEST_ID" in normalized
        assert "INSERTED.CHECKPOINT_ID" in normalized

        assert (
            "WHERE APPROVAL_ID = %(APPROVAL_ID)S "
            "AND CONSUMPTION_STATUS = 'PENDING'"
            in normalized
        )

        assert "SELECT" not in normalized

        assert parameters == {
            "approval_id": APPROVAL_ID,
            "approved_decision": (
                expected_value
            ),
        }

        assert connection.commit_count == 1
        assert connection.rollback_count == 0

        _assert_connection_closed(
            connection,
            cursor,
        )


def test_claim_consumed_approval_fails_closed_after_read_only_diagnostic():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        fetchone_results=(
            None,
            (
                "claimed",
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
        ApprovalAlreadyConsumedError
    ):
        store.claim(
            approval_id=APPROVAL_ID,
            approved=True,
        )

    assert len(
        cursor.executions
    ) == 2

    authority_statement = (
        cursor.executions[0][0]
    )

    diagnostic_statement = (
        cursor.executions[1][0]
    )

    assert (
        "UPDATE"
        in _normalize_sql(
            authority_statement
        )
    )

    diagnostic_normalized = _normalize_sql(
        diagnostic_statement
    )

    assert "SELECT" in diagnostic_normalized
    assert "CONSUMPTION_STATUS" in diagnostic_normalized

    assert connection.commit_count == 0
    assert connection.rollback_count == 1

    _assert_connection_closed(
        connection,
        cursor,
    )


def test_claim_unknown_approval_fails_as_not_found():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        fetchone_results=(
            None,
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

    with pytest.raises(
        ApprovalCorrelationNotFoundError
    ):
        store.claim(
            approval_id=APPROVAL_ID,
            approved=False,
        )

    assert len(
        cursor.executions
    ) == 2

    assert connection.commit_count == 0
    assert connection.rollback_count == 1

    _assert_connection_closed(
        connection,
        cursor,
    )


def test_complete_is_single_claimed_to_completed_conditional_update():
    adapter_type = _load_adapter_class()

    cursor = FakeCursor(
        fetchone_results=(
            (
                APPROVAL_ID,
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

    store.complete(
        APPROVAL_ID
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
        "UPDATE DBO.PENDING_APPROVALS"
        in normalized
    )

    assert (
        "CONSUMPTION_STATUS = 'COMPLETED'"
        in normalized
    )

    assert "OUTPUT" in normalized

    assert (
        "WHERE APPROVAL_ID = %(APPROVAL_ID)S "
        "AND CONSUMPTION_STATUS = 'CLAIMED'"
        in normalized
    )

    assert parameters == {
        "approval_id": APPROVAL_ID
    }

    assert connection.commit_count == 1
    assert connection.rollback_count == 0

    _assert_connection_closed(
        connection,
        cursor,
    )


def test_complete_outside_claimed_state_fails_closed():
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
        )
    )

    with pytest.raises(
        ApprovalAlreadyConsumedError
    ):
        store.complete(
            APPROVAL_ID
        )

    assert connection.commit_count == 0
    assert connection.rollback_count == 1

    _assert_connection_closed(
        connection,
        cursor,
    )


def test_get_consumption_record_preserves_valid_state_decision_pairs():
    adapter_type = _load_adapter_class()

    cases = (
        (
            "pending",
            None,
            (
                "pending",
                None,
            ),
        ),
        (
            "claimed",
            1,
            (
                "claimed",
                True,
            ),
        ),
        (
            "claimed",
            0,
            (
                "claimed",
                False,
            ),
        ),
        (
            "completed",
            1,
            (
                "completed",
                True,
            ),
        ),
        (
            "completed",
            0,
            (
                "completed",
                False,
            ),
        ),
    )

    connections = []

    for status, decision, expected in cases:
        cursor = FakeCursor(
            fetchone_results=(
                (
                    status,
                    decision,
                ),
            )
        )

        connection = FakeConnection(
            cursor=cursor
        )

        connections.append(
            (
                connection,
                cursor,
            )
        )

    iterator = iter(
        connection
        for connection, cursor
        in connections
    )

    store = adapter_type(
        connection_factory=(
            lambda: next(
                iterator
            )
        )
    )

    for (
        status,
        decision,
        expected,
    ), (
        connection,
        cursor,
    ) in zip(
        cases,
        connections,
        strict=True,
    ):
        assert (
            store.get_consumption_record(
                APPROVAL_ID
            )
            == expected
        )

        statement, parameters = (
            cursor.executions[0]
        )

        normalized = _normalize_sql(
            statement
        )

        assert "SELECT" in normalized
        assert "CONSUMPTION_STATUS" in normalized
        assert "APPROVED_DECISION" in normalized

        assert parameters == {
            "approval_id": APPROVAL_ID
        }

        assert connection.commit_count == 0
        assert connection.rollback_count == 0

        _assert_connection_closed(
            connection,
            cursor,
        )


def test_get_consumption_record_rejects_inconsistent_durable_state():
    adapter_type = _load_adapter_class()

    invalid_rows = (
        (
            "pending",
            1,
        ),
        (
            "claimed",
            None,
        ),
        (
            "completed",
            None,
        ),
        (
            "completed",
            2,
        ),
        (
            "unsupported",
            None,
        ),
    )

    connections = []

    for row in invalid_rows:
        cursor = FakeCursor(
            fetchone_results=(
                row,
            )
        )

        connection = FakeConnection(
            cursor=cursor
        )

        connections.append(
            (
                connection,
                cursor,
            )
        )

    iterator = iter(
        connection
        for connection, cursor
        in connections
    )

    store = adapter_type(
        connection_factory=(
            lambda: next(
                iterator
            )
        )
    )

    for connection, cursor in connections:
        with pytest.raises(
            RuntimeError
        ):
            store.get_consumption_record(
                APPROVAL_ID
            )

        _assert_connection_closed(
            connection,
            cursor,
        )


def test_invalid_inputs_fail_before_connection_creation():
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
        store.register(
            object()
        )

    with pytest.raises(
        ValueError
    ):
        store.get_by_approval_id(
            ""
        )

    with pytest.raises(
        ValueError
    ):
        store.get_by_request_id(
            " bad "
        )

    with pytest.raises(
        ValueError
    ):
        store.claim(
            approval_id=" ",
            approved=True,
        )

    with pytest.raises(
        TypeError
    ):
        store.claim(
            approval_id=APPROVAL_ID,
            approved=1,
        )

    with pytest.raises(
        ValueError
    ):
        store.complete(
            " bad"
        )

    with pytest.raises(
        ValueError
    ):
        store.get_consumption_record(
            ""
        )

    assert factory_calls == 0


def test_runtime_adapter_has_no_schema_ddl_sqlite_or_direct_driver_import():
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
        "BEGIN IMMEDIATE",
    )

    for fragment in forbidden:
        assert fragment not in normalized

    assert "OUTPUT" in normalized

    assert (
        "CONSUMPTION_STATUS = 'PENDING'"
        in normalized
    )

    assert (
        "CONSUMPTION_STATUS = 'CLAIMED'"
        in normalized
    )

    assert (
        "CONSUMPTION_STATUS = 'COMPLETED'"
        in normalized
    )

    lower_source = source.lower()

    assert "import sqlite3" not in lower_source

    assert (
        "import mssql_python"
        not in lower_source
    )

    assert (
        "from mssql_python"
        not in lower_source
    )