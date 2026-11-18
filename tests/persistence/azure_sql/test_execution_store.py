"""SQL text/transaction contracts with doubles; not Azure SQL execution evidence."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.persistence.azure_sql.execution_store import AzureSqlExecutionStore
from src.persistence.azure_sql.pending_approval_store import AzureSqlPendingApprovalStore
from src.runtime.incident_execution import IncidentExecutionConflictError
from src.runtime.incident_continuation_store import IncidentContinuationClaimError
from src.runtime.incident_continuation_recovery import ContinuationRecoveryCandidate
from tests.persistence.azure_sql.test_azure_sql_incident_continuation_store import FakeConnection, FakeCursor
from tests.runtime.test_incident_execution_queue import affinity, CODEC
from tests.runtime._neutral_incident_case import decision_context


def execution_row():
    scope = affinity()
    return ("wf-one", "f"*64, scope.fingerprint, json.dumps(scope.to_document()))


def job_row(status="pending", attempt=0, owner=None):
    invocation = decision_context(SimpleNamespace(approval_id="apr-one", conversation_id="conversation"), decision="reject")
    return ("apr-one", CODEC.encode(invocation), status, attempt, owner, None, 1.0, 2.0, "wf-one")


def approval_row(status="pending", decision=None):
    return ("apr-one", "wf-one", "request", "checkpoint", status, decision)


def adapters(rows=()):
    cursor = FakeCursor(fetchone_results=rows)
    connection = FakeConnection(cursor=cursor)
    connection.autocommit = False
    factory = lambda: connection
    approvals = AzureSqlPendingApprovalStore(connection_factory=factory)
    queue = AzureSqlExecutionStore(connection_factory=factory, execution_affinity=affinity(),
                                   payload_codec=CODEC, approval_store=approvals)
    return queue, approvals, connection, cursor


def sqls(cursor):
    return [" ".join(sql.upper().split()) for sql, _ in cursor.executions]


def claim_rows():
    return [("apr-one",), job_row(), execution_row(), job_row("claimed", 1, "worker"), execution_row()]


def assert_closed(connection, cursor, *, committed=1, rolled_back=0):
    assert (connection.commit_count, connection.rollback_count, connection.close_count, cursor.close_count) == (
        committed, rolled_back, 1, 1)


def test_affinity_selection_and_lock_precede_counter_update_in_one_transaction():
    queue, _, conn, cur = adapters(claim_rows())
    job = queue.claim_next(worker_id="worker")
    assert job.attempt_count == 1 and job.execution_id == "wf-one"
    statements = sqls(cur)
    assert "SELECT TOP (1)" in statements[0]
    assert "WITH (UPDLOCK, READPAST, READCOMMITTEDLOCK)" in statements[0]
    assert "ROWLOCK" not in statements[0]
    assert "E.AFFINITY_SHA256 = %(AFFINITY)S" in statements[0]
    assert "E.EXECUTION_ID = Q.EXECUTION_ID" in statements[0]
    assert cur.executions[0][1] == {"affinity": affinity().fingerprint}
    assert "WITH (UPDLOCK, HOLDLOCK)" in statements[1]
    assert "WITH (UPDLOCK, HOLDLOCK)" in statements[2]
    assert statements[3].startswith("UPDATE DBO.INCIDENT_AFFINE_CONTINUATION_JOBS")
    assert "ATTEMPT_COUNT = %(ATTEMPT)S" in statements[3]
    assert cur.executions[3][1]["attempt"] == 0
    assert_closed(conn, cur)


def test_incompatible_selector_result_does_not_execute_update():
    queue, _, conn, cur = adapters([None])
    assert queue.claim_next(worker_id="foreign") is None
    assert len(cur.executions) == 1 and "UPDATE " not in sqls(cur)[0]
    assert_closed(conn, cur)


@pytest.mark.parametrize("statement", [1,2,3,4,5,6])
def test_claim_sql_error_rolls_back_without_retry(statement):
    queue, _, conn, cur = adapters(claim_rows())
    cur.execute_error_at, cur.execute_error = statement, OSError("injected")
    with pytest.raises(OSError): queue.claim_next(worker_id="worker")
    assert len(cur.executions) == statement
    assert_closed(conn, cur, committed=0, rolled_back=1)


@pytest.mark.parametrize("failure", ["fetch", "commit", "cursor", "close"])
def test_transaction_lifecycle_failure_closes_connection(failure, monkeypatch):
    queue, _, conn, cur = adapters(claim_rows())
    def fail(): raise OSError("injected")
    if failure == "fetch": monkeypatch.setattr(cur, "fetchone", fail)
    elif failure == "close": monkeypatch.setattr(cur, "close", fail)
    else: monkeypatch.setattr(conn, failure, fail)
    with pytest.raises(OSError): queue.claim_next(worker_id="worker")
    assert conn.close_count == 1
    assert conn.commit_count == (1 if failure == "close" else 0)
    assert conn.rollback_count == (0 if failure == "close" else 1)


@pytest.mark.parametrize("setting", [True, None, "absent"])
def test_autocommit_must_be_explicitly_disabled_before_sql(setting):
    queue, _, conn, cur = adapters()
    if setting == "absent": del conn.autocommit
    else: conn.autocommit = setting
    with pytest.raises(RuntimeError, match="autocommit"):
        queue.claim_next(worker_id="worker")
    assert cur.executions == [] and conn.close_count == 1


def test_admission_holds_absent_key_range_before_insert_and_commits_once():
    queue, _, conn, cur = adapters([None])
    record = queue.admit(execution_id="wf-one", input_sha256="f"*64)
    assert record.affinity == affinity()
    assert "WITH (UPDLOCK, HOLDLOCK)" in sqls(cur)[0]
    assert sqls(cur)[1].startswith("INSERT INTO DBO.INCIDENT_EXECUTIONS")
    assert cur.executions[1][1]["affinity_sha256"] == affinity().fingerprint
    assert_closed(conn, cur)


@pytest.mark.parametrize("change", ["input", "fingerprint", "document", "identity"])
def test_admission_collision_or_corruption_never_updates_record(change):
    row = list(execution_row())
    index,value={"input":(1,"e"*64),"fingerprint":(2,"e"*64),"document":(3,"{}"),"identity":(0,"wf-other")}[change]
    row[index]=value
    queue, _, conn, cur = adapters([tuple(row)])
    with pytest.raises(ValueError): queue.admit(execution_id="wf-one", input_sha256="f"*64)
    assert len(cur.executions) == 1
    assert_closed(conn, cur, committed=0, rolled_back=1)


def test_enqueue_pins_existing_correlation_and_uses_queue_first_lock_order():
    queue, _, conn, cur = adapters([None, approval_row(), execution_row(), job_row(), execution_row()])
    invocation = CODEC.decode(job_row()[1])
    assert queue.enqueue(invocation).execution_id == "wf-one"
    assert "FROM DBO.INCIDENT_AFFINE_CONTINUATION_JOBS" in sqls(cur)[0]
    assert "FROM DBO.PENDING_APPROVALS" in sqls(cur)[1]
    insert, params = cur.executions[3]
    assert params["execution_id"] == "wf-one" and params["approval_id"] == "apr-one"
    assert "INSERT INTO dbo.incident_affine_continuation_jobs" in insert
    assert_closed(conn, cur)


def test_hitl_claim_locks_original_job_and_pending_correlation_before_consumption():
    queue, approvals, conn, cur = adapters([
        job_row("claimed",1,"worker"), execution_row(), approval_row(), approval_row("claimed",False)])
    correlation = queue.claim_approval(approval_id="apr-one",worker_id="worker",expected_attempt_count=1,
                                       approved=False,approval_store=approvals)
    assert correlation.workflow_id == "wf-one"
    statements=sqls(cur)
    assert "INCIDENT_AFFINE_CONTINUATION_JOBS WITH (UPDLOCK, HOLDLOCK)" in statements[0]
    assert "PENDING_APPROVALS WITH (UPDLOCK, HOLDLOCK)" in statements[2]
    assert "WORKFLOW_ID = %(EXECUTION)S" in statements[3]
    assert "APPROVED_DECISION IS NULL" in statements[3]
    assert cur.executions[3][1]["decision"] is False
    assert_closed(conn,cur)


def test_recovery_applies_scope_before_limit_without_payload_decoding():
    queue, _, conn, cur = adapters()
    cur.fetchall=lambda: [("apr-one","worker",1,2.0)]
    candidate,=queue.list_stale_claims(stale_before=3,limit=1,after_id="previous")
    assert candidate==ContinuationRecoveryCandidate("apr-one","worker",1,2.0)
    sql=sqls(cur)[0]
    assert "TOP (%(LIMIT)S)" in sql and "PAYLOAD" not in sql
    assert "E.AFFINITY_SHA256 = %(AFFINITY)S" in sql
    assert cur.executions[0][1]==dict(limit=1,cutoff=3,after="previous",affinity=affinity().fingerprint)
    assert_closed(conn,cur)


@pytest.mark.parametrize("change", ["same", "owner", "attempt", "timestamp", "foreign"])
def test_recovery_preserves_original_generation_and_affinity(change):
    job=list(job_row("claimed",1,"worker")); record=list(execution_row())
    if change=="owner": job[4]="other"
    if change=="attempt": job[3]=2
    if change=="timestamp": job[7]=2.5
    if change=="foreign": record[2]="e"*64
    queue,approvals,conn,cur=adapters([tuple(job),tuple(record),approval_row(),job_row("pending",1),execution_row()])
    def run():
        queue.recover_stale_before_approval(candidate=ContinuationRecoveryCandidate("apr-one","worker",1,2),
                                            stale_before=3,approval_store=approvals)
    if change=="same":
        run(); assert_closed(conn,cur)
        assert "ATTEMPT_COUNT = %(ATTEMPT)S" in sqls(cur)[3]
    else:
        with pytest.raises(IncidentContinuationClaimError): run()
        assert not any(sql.startswith("UPDATE ") for sql in sqls(cur))
        assert_closed(conn,cur,committed=0,rolled_back=1)


def test_factory_mismatch_rejected_without_opening_a_connection():
    def forbidden(): pytest.fail("No connection should open.")
    approvals=AzureSqlPendingApprovalStore(connection_factory=lambda:None)
    with pytest.raises(TypeError):
        AzureSqlExecutionStore(connection_factory=forbidden,execution_affinity=affinity(),payload_codec=CODEC,approval_store=approvals)


def test_candidate_schema_is_additive_and_has_no_historical_adoption():
    path=Path(__file__).resolve().parents[3]/"platform/azure-sql/candidates/e3_execution_affinity_v1.sql"
    sql=path.read_text().upper()
    assert "CREATE TABLE DBO.INCIDENT_EXECUTIONS" in sql
    assert "CREATE TABLE DBO.INCIDENT_AFFINE_CONTINUATION_JOBS" in sql
    assert "REFERENCES DBO.PENDING_APPROVALS(APPROVAL_ID)" in sql
    assert "REFERENCES DBO.INCIDENT_EXECUTIONS(EXECUTION_ID)" in sql
    assert "ALTER TABLE" not in sql and "INSERT INTO" not in sql and "GRANT " not in sql
