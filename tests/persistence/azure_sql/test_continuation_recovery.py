"""SQL query/transaction contracts using doubles, not a live server test."""
import pytest

from src.channels.teams.continuation_payload import TEAMS_CONTINUATION_CODEC
from src.persistence.azure_sql.incident_continuation_store import AzureSqlIncidentContinuationStore
from src.persistence.azure_sql.pending_approval_store import AzureSqlPendingApprovalStore
from src.runtime.incident_continuation_recovery import ContinuationRecoveryCandidate as Candidate
from src.runtime.incident_continuation_store import IncidentContinuationClaimError
from tests.persistence.azure_sql.test_azure_sql_incident_continuation_store import FakeConnection, FakeCursor


CANDIDATE = Candidate("a", "owner", 2, 100)


def adapters(rows=(("pending", None), ("a", 2))):
    cursor = FakeCursor(fetchone_results=rows)
    cursor.fetchall = lambda: rows
    connection = FakeConnection(cursor=cursor)
    connection.autocommit = False
    factory = lambda: connection
    queue = AzureSqlIncidentContinuationStore(connection_factory=factory, payload_codec=TEAMS_CONTINUATION_CODEC)
    approval = AzureSqlPendingApprovalStore(connection_factory=factory)
    return queue, approval, connection, cursor


def recover(queue, approval):
    return queue.recover_stale_before_approval(candidate=CANDIDATE, stale_before=200, approval_store=approval)


def normalized(sql):
    return " ".join(sql.upper().split()).replace("( ", "(").replace(" )", ")")


def closed(connection, cursor, *, committed=0, rolled_back=1):
    assert (connection.commit_count, connection.rollback_count, connection.close_count, cursor.close_count) == (
        committed, rolled_back, 1, 1,
    )


@pytest.mark.parametrize("after_id", [None, "previous"])
def test_bounded_metadata_scan_binds_cutoff_and_exclusive_cursor(after_id):
    queue, _, connection, cursor = adapters((("a", "owner", 2, 100),))
    assert queue.list_stale_claims(stale_before=200, limit=3, after_id=after_id) == (CANDIDATE,)
    sql, params = cursor.executions[0]
    sql = normalized(sql)
    assert "TOP (%(LIMIT)S) APPROVAL_ID, CLAIMED_BY, ATTEMPT_COUNT, UPDATED_AT" in sql
    assert "STATUS = 'CLAIMED' AND UPDATED_AT < %(STALE_BEFORE)S" in sql
    assert "APPROVAL_ID > %(AFTER_ID)S" in sql and "ORDER BY APPROVAL_ID ASC" in sql
    assert "PAYLOAD" not in sql and "UPDATE " not in sql
    assert params == dict(limit=3, stale_before=200, after_id=after_id)
    closed(connection, cursor, committed=1, rolled_back=0)


def test_recovery_holds_approval_lock_and_cas_guards_until_commit_without_readback(monkeypatch):
    queue, approval, connection, cursor = adapters()
    monkeypatch.setattr(approval, "get_consumption_record", lambda *a: pytest.fail("No separate read permission."))
    assert recover(queue, approval) is None
    assert len(cursor.executions) == 2
    guard, update = [normalized(sql) for sql, _ in cursor.executions]
    assert "PENDING_APPROVALS WITH (UPDLOCK, HOLDLOCK)" in guard
    assert "STATUS = 'CLAIMED'" in update
    assert "CLAIMED_BY = %(WORKER_ID)S" in update
    assert "ATTEMPT_COUNT = %(EXPECTED_ATTEMPT_COUNT)S" in update
    assert "ATTEMPT_COUNT < %(MAX_ATTEMPTS)S" in update
    assert "UPDATED_AT = %(EXPECTED_UPDATED_AT)S AND UPDATED_AT < %(STALE_BEFORE)S" in update
    assert "OUTPUT INSERTED.APPROVAL_ID, INSERTED.ATTEMPT_COUNT" in update
    params = cursor.executions[1][1]
    assert {key: params[key] for key in ("approval_id", "worker_id", "expected_attempt_count",
                                       "max_attempts", "expected_updated_at", "stale_before")} == dict(
        approval_id="a", worker_id="owner", expected_attempt_count=2,
        max_attempts=3, expected_updated_at=100, stale_before=200,
    )
    closed(connection, cursor, committed=1, rolled_back=0)


@pytest.mark.parametrize("guard", [None, ("claimed", 1), ("completed", 0), ("pending", 1)])
def test_non_pending_guard_never_updates_queue(guard):
    queue, approval, connection, cursor = adapters((guard,))
    with pytest.raises(IncidentContinuationClaimError):
        recover(queue, approval)
    assert len(cursor.executions) == 1
    closed(connection, cursor)


@pytest.mark.parametrize("output,error", [(None, IncidentContinuationClaimError),
                                         (("a", 3), RuntimeError), (("other", 2), RuntimeError)])
def test_no_output_or_changed_generation_rolls_back(output, error):
    queue, approval, connection, cursor = adapters((("pending", None), output))
    with pytest.raises(error):
        recover(queue, approval)
    closed(connection, cursor)


@pytest.mark.parametrize("failure", ["first_statement", "update", "fetch", "commit", "cursor"])
def test_each_transaction_failure_rolls_back_closes_and_never_retries(monkeypatch, failure):
    queue, approval, connection, cursor = adapters()
    def fail(*a, **kw):
        raise OSError("injected")
    if failure in ("first_statement", "update"):
        cursor.execute_error_at = 1 if failure == "first_statement" else 2
        cursor.execute_error = OSError("injected")
    elif failure == "fetch":
        monkeypatch.setattr(cursor, "fetchone", fail)
    else:
        monkeypatch.setattr(connection, failure, fail)
    with pytest.raises(OSError):
        recover(queue, approval)
    assert connection.close_count == connection.rollback_count == 1
    assert cursor.close_count == (0 if failure == "cursor" else 1)
    assert connection.commit_count == 0
    assert len(cursor.executions) <= 2


@pytest.mark.parametrize("failure", ["execute", "fetchall", "commit", "invalid_row"])
def test_scan_failure_closes_transaction_without_recovery(monkeypatch, failure):
    queue, _, connection, cursor = adapters((("a", "owner", 2, 100),))
    def fail(*a, **kw):
        raise OSError("injected")
    if failure == "invalid_row":
        cursor.fetchall = lambda: [("a", "owner", 0, 100)]
    elif failure == "commit":
        monkeypatch.setattr(connection, "commit", fail)
    else:
        monkeypatch.setattr(cursor, failure, fail)
    with pytest.raises((OSError, ValueError)):
        queue.list_stale_claims(stale_before=200, limit=1)
    closed(connection, cursor)


@pytest.mark.parametrize("autocommit", [True, None, "missing"])
def test_unknown_or_enabled_autocommit_rejected_before_any_sql(autocommit):
    queue, approval, connection, cursor = adapters()
    if autocommit == "missing":
        del connection.autocommit
    else:
        connection.autocommit = autocommit
    with pytest.raises(RuntimeError, match="autocommit"):
        recover(queue, approval)
    assert cursor.executions == [] and connection.close_count == 1


def test_wrong_factory_is_rejected_before_connection_is_opened():
    def forbidden():
        pytest.fail("No connection should open for mismatched stores.")
    queue = AzureSqlIncidentContinuationStore(connection_factory=forbidden, payload_codec=TEAMS_CONTINUATION_CODEC)
    approval = AzureSqlPendingApprovalStore(connection_factory=lambda: None)
    with pytest.raises(TypeError):
        recover(queue, approval)


@pytest.mark.parametrize("operation", ["scan", "recover"])
def test_connection_closes_even_if_cursor_close_raises(monkeypatch, operation):
    queue, approval, connection, cursor = adapters()
    cursor.fetchall = lambda: [("a", "owner", 2, 100)]
    def close_error():
        raise OSError("cursor close")
    monkeypatch.setattr(cursor, "close", close_error)
    with pytest.raises(OSError):
        if operation == "scan":
            queue.list_stale_claims(stale_before=200, limit=1)
        else:
            recover(queue, approval)
    assert connection.close_count == connection.commit_count == 1
