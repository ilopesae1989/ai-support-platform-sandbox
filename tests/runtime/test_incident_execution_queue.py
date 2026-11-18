"""Real SQLite transactions; synthetic authorized inputs, no network or effects."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import sqlite3
from types import SimpleNamespace

import pytest

from src.persistence.sqlite.execution_store import SqliteExecutionStore
from src.persistence.sqlite.incident_continuation_store import SqliteIncidentContinuationStore
from src.runtime.execution_affinity import ExecutionAffinity, ProductReleaseIdentity
from src.runtime.incident_execution import IncidentExecutionConflictError
from src.runtime.incident_continuation_codec import ContinuationPayloadCodec
from src.runtime.incident_continuation_store import IncidentContinuationClaimError, IncidentContinuationConflictError
from src.runtime.incident_continuation_recovery import IncidentContinuationRecovery
from src.runtime.procedure.approval_context import AuthorizedApprovalContext
from src.runtime.procedure.approval_channel import ApprovalDecision
from src.runtime.procedure.approval_correlation import PendingApprovalCorrelation
from src.runtime.procedure.approval_store import SqlitePendingApprovalStore, ApprovalAlreadyConsumedError
from tests.runtime._neutral_incident_case import decision_context

CODEC = ContinuationPayloadCodec(invocation_type=AuthorizedApprovalContext)


def affinity():
    return ExecutionAffinity(installation_id="a", release=ProductReleaseIdentity(
        release_id="n", source_sha256="a"*64, environment_sha256="b"*64),
        foundry_sha256="c"*64, procedures_sha256="d"*64)


def stores(tmp_path, scope=None):
    path = tmp_path / "state.db"
    approvals = SqlitePendingApprovalStore(path)
    queue = SqliteExecutionStore(path, execution_affinity=scope or affinity(),
                                payload_codec=CODEC, approval_store=approvals)
    return queue, approvals, path


def prepare(queue, approvals, name="one", decision="reject"):
    execution_id, approval_id = "wf-"+name, "apr-"+name
    queue.admit(execution_id=execution_id, input_sha256="f"*64)
    approvals.register(PendingApprovalCorrelation(approval_id=approval_id, workflow_id=execution_id,
        request_id="req-"+name, checkpoint_id="cp-"+name))
    invocation = decision_context(SimpleNamespace(approval_id=approval_id, conversation_id="conversation"), decision=decision)
    queue.enqueue(invocation)
    return invocation


def snapshot(path):
    with sqlite3.connect(path) as conn:
        return tuple(tuple(conn.execute("SELECT * FROM "+table+" ORDER BY 1")) for table in (
            "incident_executions", "incident_affine_continuation_jobs", "pending_approvals"))


@pytest.mark.parametrize("change", ["installation", "release", "code", "environment", "foundry", "procedures"])
def test_foreign_consumer_leaves_queue_owner_attempt_and_approval_untouched(tmp_path, change):
    queue, approvals, path = stores(tmp_path)
    invocation = prepare(queue, approvals)
    original = queue.execution_affinity
    modifications = {
        "installation": dict(installation_id="b"),
        "release": dict(release=replace(original.release, release_id="n-plus-one")),
        "code": dict(release=replace(original.release, source_sha256="e"*64)),
        "environment": dict(release=replace(original.release, environment_sha256="e"*64)),
        "foundry": dict(foundry_sha256="e"*64), "procedures": dict(procedures_sha256="e"*64),
    }
    foreign = SqliteExecutionStore(path, execution_affinity=replace(original, **modifications[change]),
                                  payload_codec=CODEC, approval_store=approvals)
    before = snapshot(path)
    for _ in range(4):
        assert foreign.claim_next(worker_id="foreign") is None
        assert foreign.list_stale_claims(stale_before=1e20, limit=10) == ()
    assert snapshot(path) == before
    with pytest.raises(IncidentExecutionConflictError):
        foreign.enqueue(invocation)
    assert snapshot(path) == before
    claimed = queue.claim_next(worker_id="right")
    assert claimed.attempt_count == 1 and claimed.execution_id == "wf-one"


def test_assignment_is_immutable_idempotent_and_survives_reopen(tmp_path):
    queue, approvals, path = stores(tmp_path)
    record = queue.admit(execution_id="wf-one", input_sha256="f"*64)
    assert queue.admit(execution_id="wf-one", input_sha256="f"*64) == record
    reopened = SqliteExecutionStore(path, execution_affinity=affinity(), payload_codec=CODEC, approval_store=approvals)
    assert reopened.get_execution("wf-one") == record
    with pytest.raises(IncidentExecutionConflictError):
        reopened.admit(execution_id="wf-one", input_sha256="e"*64)
    assert reopened.get_execution("wf-one") == record


@pytest.mark.parametrize("corruption", ["digest", "json", "duplicate", "input-digest"])
def test_corrupt_admission_rolls_back_claim_before_attempt_increment(tmp_path, corruption):
    queue, approvals, path = stores(tmp_path)
    prepare(queue, approvals)
    with sqlite3.connect(path) as conn:
        if corruption == "digest":
            conn.execute("UPDATE incident_executions SET affinity_sha256=?", ("e"*64,))
        elif corruption == "json":
            conn.execute("UPDATE incident_executions SET affinity_json='{}'")
        elif corruption == "duplicate":
            value = json.dumps(affinity().to_document())[:-1]+',"schema_version":"execution-affinity-v1"}'
            conn.execute("UPDATE incident_executions SET affinity_json=?", (value,))
        else:
            conn.execute("UPDATE incident_executions SET input_sha256='bad'")
    before = snapshot(path)
    if corruption == "digest":
        assert queue.claim_next(worker_id="worker") is None
    else:
        with pytest.raises(ValueError):
            queue.claim_next(worker_id="worker")
    assert snapshot(path) == before


def test_legacy_and_candidate_consumers_cannot_claim_each_others_rows(tmp_path):
    queue, approvals, path = stores(tmp_path)
    legacy = SqliteIncidentContinuationStore(path, payload_codec=CODEC)
    prepare(queue, approvals)
    assert legacy.claim_next(worker_id="old") is None
    old = decision_context(SimpleNamespace(approval_id="old", conversation_id="conversation"), decision="reject")
    legacy.enqueue(old)
    assert queue.claim_next(worker_id="new").approval_id == "apr-one"
    assert queue.claim_next(worker_id="new") is None
    assert legacy.claim_next(worker_id="old").approval_id == "old"


def test_missing_admission_cannot_adopt_historical_approval(tmp_path):
    queue, approvals, path = stores(tmp_path)
    approvals.register(PendingApprovalCorrelation(approval_id="old", workflow_id="wf-old", request_id="r", checkpoint_id="c"))
    action = decision_context(SimpleNamespace(approval_id="old", conversation_id="conversation"), decision="reject")
    before = snapshot(path)
    with pytest.raises(KeyError):
        queue.enqueue(action)
    assert snapshot(path) == before


def test_duplicate_handoff_is_idempotent_but_changed_decision_conflicts(tmp_path):
    queue, approvals, path = stores(tmp_path)
    action = prepare(queue, approvals)
    before = snapshot(path)
    assert queue.enqueue(action).attempt_count == 0
    changed = action.model_copy(update={"action": action.action.model_copy(update={"decision": ApprovalDecision.APPROVE})})
    with pytest.raises(IncidentContinuationConflictError):
        queue.enqueue(changed)
    assert snapshot(path) == before


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_owned_hitl_claim_is_monotonic_and_recovery_does_not_reopen_it(tmp_path, decision):
    queue, approvals, path = stores(tmp_path)
    prepare(queue, approvals, decision=decision)
    job = queue.claim_next(worker_id="worker")
    kwargs = dict(approval_id=job.approval_id, worker_id="worker", expected_attempt_count=1, approval_store=approvals)
    correlation = queue.claim_approval(**kwargs, approved=decision == "approve")
    assert correlation.workflow_id == job.execution_id
    before = snapshot(path)
    with pytest.raises(ApprovalAlreadyConsumedError):
        queue.claim_approval(**kwargs, approved=decision == "approve")
    with pytest.raises(IncidentContinuationClaimError):
        queue.recover_claimed_before_approval(**kwargs)
    assert snapshot(path) == before
    approvals.complete(job.approval_id)
    assert queue.complete(**{k:v for k,v in kwargs.items() if k!="approval_store"}).status.value == "completed"


def test_foreign_recovery_cannot_list_or_adopt_an_original_candidate(tmp_path):
    queue, approvals, path = stores(tmp_path)
    prepare(queue, approvals)
    queue.claim_next(worker_id="worker")
    candidate, = queue.list_stale_claims(stale_before=1e20, limit=10)
    foreign = SqliteExecutionStore(path, execution_affinity=replace(affinity(), installation_id="b"),
                                  payload_codec=CODEC, approval_store=approvals)
    before = snapshot(path)
    assert foreign.list_stale_claims(stale_before=1e20, limit=10) == ()
    with pytest.raises(IncidentContinuationClaimError):
        foreign.recover_stale_before_approval(candidate=candidate, stale_before=1e20, approval_store=approvals)
    assert snapshot(path) == before
    result = IncidentContinuationRecovery(continuation_store=queue, approval_store=approvals).run_batch(
        stale_before=1e20, limit=10)
    assert result.results[0].outcome.value == "requeued"
    assert queue.get("apr-one").attempt_count == 1


@pytest.mark.parametrize("transition", ["complete", "fail", "recover", "hitl", "stale"])
def test_previous_owner_generation_cannot_mutate_reclaimed_job(tmp_path, transition):
    queue, approvals, path = stores(tmp_path)
    prepare(queue, approvals)
    first = queue.claim_next(worker_id="same")
    candidate, = queue.list_stale_claims(stale_before=1e20, limit=10)
    args = dict(approval_id=first.approval_id, worker_id="same", expected_attempt_count=1)
    queue.recover_claimed_before_approval(**args, approval_store=approvals)
    assert queue.claim_next(worker_id="same").attempt_count == 2
    before = snapshot(path)
    with pytest.raises(IncidentContinuationClaimError):
        if transition == "complete": queue.complete(**args)
        elif transition == "fail": queue.fail(**args, error="old")
        elif transition == "recover": queue.recover_claimed_before_approval(**args, approval_store=approvals)
        elif transition == "hitl": queue.claim_approval(**args, approved=False, approval_store=approvals)
        else: queue.recover_stale_before_approval(candidate=candidate, stale_before=1e20, approval_store=approvals)
    assert snapshot(path) == before


def test_concurrent_consumers_obtain_one_generation(tmp_path):
    queue, approvals, path = stores(tmp_path)
    prepare(queue, approvals)
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = list(pool.map(lambda n: queue.claim_next(worker_id="worker-"+str(n)), range(4)))
    assert sum(job is not None for job in jobs) == 1
    assert queue.get("apr-one").attempt_count == 1


def test_recovery_budget_preserved_at_three_attempts(tmp_path):
    queue, approvals, path = stores(tmp_path)
    prepare(queue, approvals)
    for attempt in range(1, 4):
        job = queue.claim_next(worker_id="worker")
        assert job.attempt_count == attempt
        args = dict(approval_id=job.approval_id, worker_id="worker", expected_attempt_count=attempt, approval_store=approvals)
        if attempt < 3:
            queue.recover_claimed_before_approval(**args)
        else:
            before = snapshot(path)
            with pytest.raises(IncidentContinuationClaimError): queue.recover_claimed_before_approval(**args)
            assert snapshot(path) == before


def test_separate_approval_file_is_rejected(tmp_path):
    approvals = SqlitePendingApprovalStore(tmp_path / "a.db")
    with pytest.raises(TypeError):
        SqliteExecutionStore(tmp_path / "b.db", execution_affinity=affinity(), payload_codec=CODEC, approval_store=approvals)
    assert not (tmp_path / "b.db").exists()


def test_claim_commit_acknowledgement_loss_never_reclaims_same_row(tmp_path, monkeypatch):
    queue, approvals, path = stores(tmp_path)
    prepare(queue, approvals)
    connect = queue._connect
    calls = []
    class LostAcknowledgement:
        def __init__(self): self.connection = connect()
        def cursor(self): return self.connection.cursor()
        def commit(self):
            self.connection.commit()
            calls.append("commit")
            raise OSError("acknowledgement lost")
        def rollback(self): self.connection.rollback()
        def close(self): self.connection.close()
    monkeypatch.setattr(queue, "_connect", LostAcknowledgement)
    with pytest.raises(OSError): queue.claim_next(worker_id="worker")
    monkeypatch.setattr(queue, "_connect", connect)
    assert calls == ["commit"]
    assert queue.claim_next(worker_id="next") is None
    assert queue.get("apr-one").attempt_count == 1
    assert approvals.get_consumption_record("apr-one") == ("pending", None)


def test_recovery_excludes_foreign_rows_before_applying_batch_limit(tmp_path):
    queue, approvals, path = stores(tmp_path)
    foreign = SqliteExecutionStore(path, execution_affinity=replace(affinity(), installation_id="b"),
                                  payload_codec=CODEC, approval_store=approvals)
    prepare(foreign, approvals, "a-foreign")
    foreign.claim_next(worker_id="foreign")
    prepare(queue, approvals, "z-local")
    queue.claim_next(worker_id="local")
    batch = queue.list_stale_claims(stale_before=1e20, limit=1)
    assert len(batch) == 1 and batch[0].approval_id == "apr-z-local"
    assert queue.list_stale_claims(stale_before=1e20, limit=1, after_id=batch[0].approval_id) == ()


@pytest.mark.parametrize("first_is_drain", [False, True])
def test_drain_serializes_with_admission_and_survives_restart(tmp_path, monkeypatch, first_is_drain):
    from threading import Event
    from src.runtime.incident_execution import AdmissionClosedError

    first, approvals, path = stores(tmp_path)
    def reopen(scope):
        return SqliteExecutionStore(path, execution_affinity=scope, payload_codec=CODEC, approval_store=approvals)

    second = reopen(first.execution_affinity)
    def admit(store):
        return store.admit(execution_id="wf-race", input_sha256="f"*64)

    # Hold the first writer inside the transaction until the second begins its write transaction.
    locked, contending = Event(), Event()
    check = first._is_draining
    def hold(cursor, scope):
        value = check(cursor, scope)
        locked.set()
        assert contending.wait(10)
        return value
    connect = second._connect
    def observed_connection():
        connection = connect()
        connection.set_trace_callback(lambda sql: contending.set() if sql == "BEGIN IMMEDIATE" else None)
        return connection
    monkeypatch.setattr(first, "_is_draining", hold)
    monkeypatch.setattr(second, "_connect", observed_connection)
    with ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(first.begin_drain if first_is_drain else lambda: admit(first))
        assert locked.wait(10)
        follower = pool.submit(lambda: admit(second)) if first_is_drain else pool.submit(second.begin_drain)
        leader.result(timeout=15)
        if first_is_drain:
            with pytest.raises(AdmissionClosedError):
                follower.result(timeout=15)
        else:
            follower.result(timeout=15)

    reopened = reopen(first.execution_affinity)
    reopened.begin_drain()
    if first_is_drain:
        with pytest.raises(KeyError):
            reopened.get_execution("wf-race")
    else:
        assert admit(reopened) == reopened.get_execution("wf-race")
    with pytest.raises(AdmissionClosedError):
        reopened.admit(execution_id="new", input_sha256="e"*64)
    other = reopen(replace(first.execution_affinity, installation_id="other-client"))
    other.admit(execution_id="other", input_sha256="e"*64)
