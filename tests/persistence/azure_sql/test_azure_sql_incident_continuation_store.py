from __future__ import annotations

import importlib
import inspect
import json

from pathlib import Path

import pytest

from src.channels.teams.approval_authorization import (
    AuthorizedTeamsApprovalInvocation,
)

from src.channels.teams.incident_continuation_store import (
    IncidentContinuationClaimError,
    IncidentContinuationConflictError,
    IncidentContinuationStatus,
)

from src.channels.teams.operator_identity import (
    TeamsOperatorIdentity,
)

from src.runtime.procedure.approval_channel import (
    ApprovalChannelAction,
    ApprovalDecision,
)


MODULE_NAME = (
    "src.persistence.azure_sql."
    "incident_continuation_store"
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
    / "incident_continuation_store.py"
)


APPROVAL_ID = "apr-azure-continuation-001"
WORKER_ID = "worker-azure-001"


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


class FakeApprovalStore:
    def __init__(
        self,
        record,
    ):
        self.record = record
        self.calls = []

    def get_consumption_record(
        self,
        approval_id,
    ):
        self.calls.append(
            approval_id
        )

        return self.record


def _invocation(
    *,
    approval_id=APPROVAL_ID,
    decision=ApprovalDecision.APPROVE,
    aad_object_id="aad-azure-continuation-001",
):
    return AuthorizedTeamsApprovalInvocation(
        policy_id="teams-hitl-sandbox-v1",

        operator=TeamsOperatorIdentity(
            tenant_id="tenant-azure-continuation-001",
            aad_object_id=aad_object_id,
            teams_user_id="teams-user-azure-continuation-001",
            conversation_id="conversation-azure-continuation-001",
            display_name="Azure Continuation Tester",
        ),

        action=ApprovalChannelAction(
            approval_id=approval_id,
            decision=decision,
        ),
    )


def _canonical_payload(
    invocation,
):
    return json.dumps(
        invocation.model_dump(
            mode="json"
        ),
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )


def _job_row(
    *,
    invocation=None,
    status="pending",
    attempt_count=0,
    claimed_by=None,
    last_error=None,
    created_at=100.0,
    updated_at=100.0,
):
    if invocation is None:
        invocation = _invocation()

    return (
        invocation.action.approval_id,
        _canonical_payload(
            invocation
        ),
        status,
        attempt_count,
        claimed_by,
        last_error,
        created_at,
        updated_at,
    )


def _load_adapter_class():
    assert MODULE_PATH.is_file(), (
        "Debe existir "
        "src/persistence/azure_sql/"
        "incident_continuation_store.py"
    )

    module = importlib.import_module(
        MODULE_NAME
    )

    adapter = getattr(
        module,
        "AzureSqlIncidentContinuationStore",
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


def _assert_closed(
    connection,
    cursor,
):
    assert connection.close_count == 1
    assert cursor.close_count == 1


def test_azure_sql_incident_continuation_store_exists():
    adapter = _load_adapter_class()

    signature = inspect.signature(
        adapter
    )

    assert (
        "connection_factory"
        in signature.parameters
    )

    assert (
        signature.parameters[
            "connection_factory"
        ].kind
        is inspect.Parameter.KEYWORD_ONLY
    )


def test_enqueue_new_job_uses_parameterized_insert_output_and_commits():
    adapter_type = _load_adapter_class()

    invocation = _invocation()

    cursor = FakeCursor(
        fetchone_results=(
            _job_row(
                invocation=invocation
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

    queued = store.enqueue(
        invocation
    )

    assert (
        queued.status
        == IncidentContinuationStatus.PENDING
    )

    assert queued.invocation == invocation
    assert queued.attempt_count == 0

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
        "DBO.INCIDENT_CONTINUATION_JOBS"
        in normalized
    )

    assert "OUTPUT" in normalized

    assert parameters[
        "approval_id"
    ] == APPROVAL_ID

    assert parameters[
        "payload_json"
    ] == _canonical_payload(
        invocation
    )

    assert parameters[
        "status"
    ] == "pending"

    assert parameters[
        "attempt_count"
    ] == 0

    assert parameters[
        "claimed_by"
    ] is None

    assert parameters[
        "last_error"
    ] is None

    assert isinstance(
        parameters[
            "created_at"
        ],
        float,
    )

    assert (
        parameters[
            "created_at"
        ]
        == parameters[
            "updated_at"
        ]
    )

    assert connection.commit_count == 1
    assert connection.rollback_count == 0

    _assert_closed(
        connection,
        cursor,
    )


def test_enqueue_exact_duplicate_is_idempotent_after_unique_conflict():
    adapter_type = _load_adapter_class()

    invocation = _invocation()

    cursor = FakeCursor(
        fetchone_results=(
            _job_row(
                invocation=invocation
            ),
        ),
        execute_error_at=1,
        execute_error=(
            FakeIntegrityError(
                "duplicate primary key"
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

    restored = store.enqueue(
        invocation
    )

    assert restored.invocation == invocation

    assert (
        restored.status
        == IncidentContinuationStatus.PENDING
    )

    assert len(
        cursor.executions
    ) == 2

    assert connection.rollback_count == 1

    _assert_closed(
        connection,
        cursor,
    )


def test_enqueue_same_approval_with_different_payload_fails_closed():
    adapter_type = _load_adapter_class()

    requested = _invocation(
        decision=(
            ApprovalDecision.REJECT
        )
    )

    existing = _invocation(
        decision=(
            ApprovalDecision.APPROVE
        )
    )

    cursor = FakeCursor(
        fetchone_results=(
            _job_row(
                invocation=existing
            ),
        ),
        execute_error_at=1,
        execute_error=(
            FakeIntegrityError(
                "duplicate primary key"
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
        IncidentContinuationConflictError
    ):
        store.enqueue(
            requested
        )

    assert connection.rollback_count == 1

    _assert_closed(
        connection,
        cursor,
    )


def test_get_returns_exact_typed_job():
    adapter_type = _load_adapter_class()

    invocation = _invocation()

    cursor = FakeCursor(
        fetchone_results=(
            _job_row(
                invocation=invocation
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

    restored = store.get(
        APPROVAL_ID
    )

    assert restored.invocation == invocation

    statement, parameters = (
        cursor.executions[0]
    )

    normalized = _normalize_sql(
        statement
    )

    assert (
        "WHERE APPROVAL_ID = "
        "%(APPROVAL_ID)S"
        in normalized
    )

    assert parameters == {
        "approval_id": APPROVAL_ID
    }

    _assert_closed(
        connection,
        cursor,
    )


def test_get_missing_job_fails_closed():
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
        KeyError
    ):
        store.get(
            APPROVAL_ID
        )

    _assert_closed(
        connection,
        cursor,
    )


def test_claim_next_is_ordered_atomic_queue_update_with_output():
    adapter_type = _load_adapter_class()

    claimed_row = _job_row(
        status="claimed",
        attempt_count=1,
        claimed_by=WORKER_ID,
        updated_at=200.0,
    )

    cursor = FakeCursor(
        fetchone_results=(
            claimed_row,
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

    claimed = store.claim_next(
        worker_id=WORKER_ID
    )

    assert (
        claimed.status
        == IncidentContinuationStatus.CLAIMED
    )

    assert claimed.claimed_by == WORKER_ID
    assert claimed.attempt_count == 1

    assert len(
        cursor.executions
    ) == 1

    statement, parameters = (
        cursor.executions[0]
    )

    normalized = _normalize_sql(
        statement
    )

    assert "WITH" in normalized
    assert "SELECT TOP (1)" in normalized

    assert (
        "FROM "
        "DBO.INCIDENT_CONTINUATION_JOBS"
        in normalized
    )

    assert "UPDLOCK" in normalized
    assert "READPAST" in normalized
    assert "READCOMMITTEDLOCK" in normalized
    assert "ROWLOCK" in normalized

    assert (
        "WHERE STATUS = 'PENDING'"
        in normalized
    )

    assert (
        "ORDER BY "
        "CREATED_AT ASC, "
        "APPROVAL_ID ASC"
        in normalized
    )

    assert (
        "ATTEMPT_COUNT = "
        "ATTEMPT_COUNT + 1"
        in normalized
    )

    assert (
        "CLAIMED_BY = "
        "%(WORKER_ID)S"
        in normalized
    )

    assert "OUTPUT" in normalized

    assert parameters[
        "worker_id"
    ] == WORKER_ID

    assert isinstance(
        parameters[
            "updated_at"
        ],
        float,
    )

    assert connection.commit_count == 1
    assert connection.rollback_count == 0

    _assert_closed(
        connection,
        cursor,
    )


def test_claim_next_without_pending_job_returns_none():
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

    assert (
        store.claim_next(
            worker_id=WORKER_ID
        )
        is None
    )

    assert len(
        cursor.executions
    ) == 1

    assert connection.commit_count == 1
    assert connection.rollback_count == 0

    _assert_closed(
        connection,
        cursor,
    )


def test_complete_requires_exact_claim_owner():
    adapter_type = _load_adapter_class()

    completed_row = _job_row(
        status="completed",
        attempt_count=1,
        claimed_by=None,
        updated_at=300.0,
    )

    cursor = FakeCursor(
        fetchone_results=(
            completed_row,
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

    completed = store.complete(
        approval_id=APPROVAL_ID,
        worker_id=WORKER_ID,
    )

    assert (
        completed.status
        == IncidentContinuationStatus.COMPLETED
    )

    assert completed.claimed_by is None

    statement = (
        cursor.executions[0][0]
    )

    normalized = _normalize_sql(
        statement
    )

    assert (
        "STATUS = 'COMPLETED'"
        in normalized
    )

    assert (
        "AND STATUS = 'CLAIMED'"
        in normalized
    )

    assert (
        "AND CLAIMED_BY = "
        "%(WORKER_ID)S"
        in normalized
    )

    assert "OUTPUT" in normalized

    assert connection.commit_count == 1

    _assert_closed(
        connection,
        cursor,
    )


def test_complete_wrong_owner_or_state_fails_closed():
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
        IncidentContinuationClaimError
    ):
        store.complete(
            approval_id=APPROVAL_ID,
            worker_id=WORKER_ID,
        )

    assert connection.commit_count == 0
    assert connection.rollback_count == 1

    _assert_closed(
        connection,
        cursor,
    )


def test_fail_requires_exact_claim_owner_and_persists_error():
    adapter_type = _load_adapter_class()

    failed_row = _job_row(
        status="failed",
        attempt_count=1,
        claimed_by=None,
        last_error="PROCESSING FAILED",
        updated_at=400.0,
    )

    cursor = FakeCursor(
        fetchone_results=(
            failed_row,
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

    failed = store.fail(
        approval_id=APPROVAL_ID,
        worker_id=WORKER_ID,
        error="PROCESSING FAILED",
    )

    assert (
        failed.status
        == IncidentContinuationStatus.FAILED
    )

    assert (
        failed.last_error
        == "PROCESSING FAILED"
    )

    statement, parameters = (
        cursor.executions[0]
    )

    normalized = _normalize_sql(
        statement
    )

    assert (
        "STATUS = 'FAILED'"
        in normalized
    )

    assert (
        "LAST_ERROR = "
        "%(ERROR)S"
        in normalized
    )

    assert parameters[
        "error"
    ] == "PROCESSING FAILED"

    assert connection.commit_count == 1

    _assert_closed(
        connection,
        cursor,
    )


def test_fail_wrong_owner_or_state_fails_closed():
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
        IncidentContinuationClaimError
    ):
        store.fail(
            approval_id=APPROVAL_ID,
            worker_id=WORKER_ID,
            error="FAIL",
        )

    assert connection.commit_count == 0
    assert connection.rollback_count == 1

    _assert_closed(
        connection,
        cursor,
    )


def test_recovery_revalidates_pending_approval_under_same_sql_transaction():
    adapter_type = _load_adapter_class()

    approval_store = FakeApprovalStore(
        (
            "pending",
            None,
        )
    )

    recovered_row = _job_row(
        status="pending",
        attempt_count=1,
        claimed_by=None,
        last_error=None,
        updated_at=500.0,
    )

    cursor = FakeCursor(
        fetchone_results=(
            (
                "pending",
                None,
            ),
            recovered_row,
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

    recovered = (
        store
        .recover_claimed_before_approval(
            approval_id=APPROVAL_ID,
            worker_id=WORKER_ID,
            approval_store=approval_store,
        )
    )

    assert approval_store.calls == [
        APPROVAL_ID
    ]

    assert (
        recovered.status
        == IncidentContinuationStatus.PENDING
    )

    assert recovered.claimed_by is None
    assert recovered.attempt_count == 1

    assert len(
        cursor.executions
    ) == 2

    guard_statement = (
        cursor.executions[0][0]
    )

    recovery_statement = (
        cursor.executions[1][0]
    )

    guard_normalized = _normalize_sql(
        guard_statement
    )

    recovery_normalized = _normalize_sql(
        recovery_statement
    )

    assert (
        "FROM DBO.PENDING_APPROVALS"
        in guard_normalized
    )

    assert "UPDLOCK" in guard_normalized
    assert "HOLDLOCK" in guard_normalized

    assert (
        "CONSUMPTION_STATUS"
        in guard_normalized
    )

    assert (
        "APPROVED_DECISION"
        in guard_normalized
    )

    assert (
        "UPDATE "
        "DBO.INCIDENT_CONTINUATION_JOBS"
        in recovery_normalized
    )

    assert (
        "STATUS = 'PENDING'"
        in recovery_normalized
    )

    assert (
        "AND STATUS = 'CLAIMED'"
        in recovery_normalized
    )

    assert (
        "AND CLAIMED_BY = "
        "%(WORKER_ID)S"
        in recovery_normalized
    )

    assert "OUTPUT" in recovery_normalized

    assert connection.commit_count == 1
    assert connection.rollback_count == 0

    _assert_closed(
        connection,
        cursor,
    )


def test_recovery_consumed_precheck_fails_before_sql_connection():
    adapter_type = _load_adapter_class()

    approval_store = FakeApprovalStore(
        (
            "claimed",
            True,
        )
    )

    factory_calls = 0

    def forbidden_factory():
        nonlocal factory_calls

        factory_calls += 1

        raise AssertionError(
            "No debe conectar si approval "
            "ya esta consumido."
        )

    store = adapter_type(
        connection_factory=(
            forbidden_factory
        )
    )

    with pytest.raises(
        IncidentContinuationClaimError
    ):
        store.recover_claimed_before_approval(
            approval_id=APPROVAL_ID,
            worker_id=WORKER_ID,
            approval_store=approval_store,
        )

    assert factory_calls == 0


def test_recovery_locked_recheck_blocks_approval_race():
    adapter_type = _load_adapter_class()

    approval_store = FakeApprovalStore(
        (
            "pending",
            None,
        )
    )

    cursor = FakeCursor(
        fetchone_results=(
            (
                "claimed",
                1,
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
        IncidentContinuationClaimError
    ):
        store.recover_claimed_before_approval(
            approval_id=APPROVAL_ID,
            worker_id=WORKER_ID,
            approval_store=approval_store,
        )

    assert len(
        cursor.executions
    ) == 1

    assert connection.commit_count == 0
    assert connection.rollback_count == 1

    _assert_closed(
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
        store.enqueue(
            object()
        )

    with pytest.raises(
        ValueError
    ):
        store.get(
            ""
        )

    with pytest.raises(
        ValueError
    ):
        store.claim_next(
            worker_id=" "
        )

    with pytest.raises(
        ValueError
    ):
        store.complete(
            approval_id=" bad",
            worker_id=WORKER_ID,
        )

    with pytest.raises(
        ValueError
    ):
        store.fail(
            approval_id=APPROVAL_ID,
            worker_id=" bad ",
            error="failure",
        )

    with pytest.raises(
        ValueError
    ):
        store.fail(
            approval_id=APPROVAL_ID,
            worker_id=WORKER_ID,
            error="",
        )

    assert factory_calls == 0


def test_runtime_adapter_has_queue_hints_atomic_recovery_and_no_runtime_ddl():
    _load_adapter_class()

    source = MODULE_PATH.read_text(
        encoding="utf-8"
    )

    normalized = _normalize_sql(
        source
    )

    for forbidden in (
        "CREATE TABLE",
        "ALTER TABLE",
        "DROP TABLE",
        "CREATE DATABASE",
        "DROP DATABASE",
        "BEGIN IMMEDIATE",
        "UPDATE TOP (1)",
    ):
        assert forbidden not in normalized

    for required in (
        "READPAST",
        "UPDLOCK",
        "READCOMMITTEDLOCK",
        "ROWLOCK",
        "HOLDLOCK",
        "ORDER BY",
        "CREATED_AT ASC",
        "APPROVAL_ID ASC",
        "OUTPUT",
        "DBO.PENDING_APPROVALS",
        "DBO.INCIDENT_CONTINUATION_JOBS",
    ):
        assert required in normalized

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