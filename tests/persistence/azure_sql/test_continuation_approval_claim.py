"""SQL transaction contract only; these doubles do not certify server locks."""
import pytest

from src.persistence.azure_sql.incident_continuation_store import AzureSqlIncidentContinuationStore
from src.persistence.azure_sql.pending_approval_store import AzureSqlPendingApprovalStore
from src.runtime.incident_continuation_store import IncidentContinuationClaimError
from src.runtime.procedure.approval_store import ApprovalAlreadyConsumedError
from tests.persistence.azure_sql.test_azure_sql_incident_continuation_store import (
    FakeConnection, FakeCursor, _invocation, APPROVAL_ID, WORKER_ID,
)
from src.channels.teams.continuation_payload import TEAMS_CONTINUATION_CODEC


def adapters(rows=None):
    if rows is None:
        rows = [("pending", None), (TEAMS_CONTINUATION_CODEC.encode(_invocation()),),
                (APPROVAL_ID, "workflow", "request", "checkpoint")]
    cursor = FakeCursor(fetchone_results=rows)
    connection = FakeConnection(cursor=cursor)
    connection.autocommit = False
    factory = lambda: connection
    queue = AzureSqlIncidentContinuationStore(connection_factory=factory, payload_codec=TEAMS_CONTINUATION_CODEC)
    approval = AzureSqlPendingApprovalStore(connection_factory=factory)
    return queue, approval, connection, cursor


def claim(queue, approval, **extra):
    kwargs = dict(approval_id=APPROVAL_ID, worker_id=WORKER_ID,
                  expected_attempt_count=2, approved=True, approval_store=approval)
    kwargs.update(extra)
    return queue.claim_approval(**kwargs)


def test_single_transaction_locks_approval_then_owner_and_commits_before_return():
    queue, approval, connection, cursor = adapters()
    result = claim(queue, approval)
    assert result.approval_id == APPROVAL_ID
    assert (connection.commit_count, connection.rollback_count, connection.close_count, cursor.close_count) == (1, 0, 1, 1)
    assert len(cursor.executions) == 3
    guard, owner, update = [" ".join(sql.upper().split()).replace("( ", "(").replace(" )", ")")
                            for sql, _ in cursor.executions]
    assert "PENDING_APPROVALS WITH (UPDLOCK, HOLDLOCK)" in guard
    assert "INCIDENT_CONTINUATION_JOBS WITH (UPDLOCK, HOLDLOCK)" in owner
    assert "ATTEMPT_COUNT = %(EXPECTED_ATTEMPT_COUNT)S" in owner
    assert "CLAIMED_BY = %(WORKER_ID)S" in owner
    assert "STATUS = 'CLAIMED'" in owner
    assert "APPROVED_DECISION IS NULL" in update
    assert cursor.executions[1][1]["expected_attempt_count"] == 2


@pytest.mark.parametrize("record", [None, ("claimed", 1), ("completed", 0), ("pending", 1)])
def test_non_pending_or_inconsistent_approval_cannot_reach_queue_or_update(record):
    queue, approval, connection, cursor = adapters([record])
    with pytest.raises(ApprovalAlreadyConsumedError):
        claim(queue, approval)
    assert len(cursor.executions) == 1
    assert (connection.commit_count, connection.rollback_count, connection.close_count) == (0, 1, 1)


def test_lost_owner_rolls_back_without_consuming_approval():
    queue, approval, connection, cursor = adapters([("pending", None), None])
    with pytest.raises(IncidentContinuationClaimError):
        claim(queue, approval)
    assert len(cursor.executions) == 2
    assert connection.commit_count == 0 and connection.rollback_count == 1


def test_changed_decision_rejected_before_update():
    queue, approval, connection, cursor = adapters()
    with pytest.raises(IncidentContinuationClaimError):
        claim(queue, approval, approved=False)
    assert len(cursor.executions) == 2 and connection.commit_count == 0


def test_no_output_from_claim_update_is_not_success():
    queue, approval, connection, cursor = adapters([
        ("pending", None), (TEAMS_CONTINUATION_CODEC.encode(_invocation()),), None,
    ])
    with pytest.raises(ApprovalAlreadyConsumedError):
        claim(queue, approval)
    assert connection.rollback_count == 1 and connection.commit_count == 0


@pytest.mark.parametrize("failure_at", [1, 2, 3, "commit"])
def test_database_failure_rolls_back_closes_and_propagates_without_retry(failure_at):
    queue, approval, connection, cursor = adapters()
    if failure_at == "commit":
        def uncertain():
            connection.commit_count += 1
            raise OSError("synthetic uncertain commit")
        connection.commit = uncertain
    else:
        cursor.execute_error_at = failure_at
        cursor.execute_error = OSError("synthetic SQL failure")
    with pytest.raises(OSError):
        claim(queue, approval)
    assert connection.rollback_count == connection.close_count == cursor.close_count == 1
    assert len(cursor.executions) == (3 if failure_at == "commit" else failure_at)


def test_autocommit_cannot_silently_release_locks_between_checks():
    queue, approval, connection, cursor = adapters()
    connection.autocommit = True
    with pytest.raises(RuntimeError, match="autocommit"):
        claim(queue, approval)
    assert cursor.executions == []
    assert connection.close_count == 1 and connection.commit_count == 0


def test_mismatched_database_factory_is_rejected_before_opening_connection():
    queue, approval, connection, cursor = adapters()
    other = AzureSqlPendingApprovalStore(connection_factory=lambda: connection)
    with pytest.raises(TypeError, match="same SQL connection factory"):
        claim(queue, other)
    assert cursor.executions == [] and connection.close_count == 0
