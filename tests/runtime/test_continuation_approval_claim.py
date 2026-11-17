"""HITL consumption and queue ownership: real SQLite, synthetic workflows/SQL."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier, Event
import sqlite3

import pytest

from src.runtime.continuation_approval_store import ContinuationApprovalStore
from src.runtime.incident_continuation_codec import ContinuationPayloadCodec
from src.runtime.incident_continuation_store import IncidentContinuationClaimError
from src.runtime.incident_continuation_worker import (
    IncidentContinuationWorker, IncidentContinuationWorkerDependencies,
    IncidentContinuationWorkerOutcome,
)
from src.runtime.procedure.approval_store import SqlitePendingApprovalStore, ApprovalAlreadyConsumedError
from src.runtime.procedure.approval_correlation import PendingApprovalCorrelation
from src.runtime.procedure.authorized_approval import AuthorizedApprovalInvocation
from src.persistence.sqlite.incident_continuation_store import SqliteIncidentContinuationStore

CODEC = ContinuationPayloadCodec(invocation_type=AuthorizedApprovalInvocation)


def setup(tmp_path, *, shared=False, journal="DELETE", decision="approve"):
    ap = tmp_path / "approval.db"
    qp = ap if shared else tmp_path / "queue.db"
    approval = SqlitePendingApprovalStore(ap)
    queue = SqliteIncidentContinuationStore(qp, payload_codec=CODEC)
    for path in {ap, qp}:
        with closing(sqlite3.connect(path)) as db, db:
            assert db.execute(f"PRAGMA journal_mode={journal}").fetchone()[0].lower() == journal.lower()
    approval.register(PendingApprovalCorrelation(
        approval_id="a", workflow_id="w", request_id="r", checkpoint_id="c",
    ))
    queue.enqueue(AuthorizedApprovalInvocation(
        policy_id="p", action={"approval_id": "a", "decision": decision},
    ))
    return queue, approval


def view(queue, approval, job):
    return ContinuationApprovalStore(job=job, continuation_store=queue, approval_store=approval)


def recover(queue, approval, job):
    return queue.recover_claimed_before_approval(
        approval_id=job.approval_id, worker_id=job.claimed_by,
        expected_attempt_count=job.attempt_count, approval_store=approval,
    )


@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.parametrize("journal", ["DELETE", "WAL"])
@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_old_attempt_cannot_consume_after_recovery_and_reclaim(tmp_path, shared, journal, decision):
    queue, approval = setup(tmp_path, shared=shared, journal=journal, decision=decision)
    first = queue.claim_next(worker_id="reused-owner")
    stale = view(queue, approval, first)
    recover(queue, approval, first)
    second = queue.claim_next(worker_id="reused-owner")
    with pytest.raises(IncidentContinuationClaimError):
        stale.claim(approval_id="a", approved=decision == "approve")
    assert approval.get_consumption_record("a") == ("pending", None)
    assert queue.get("a") == second
    current = view(queue, approval, second)
    assert current.claim(approval_id="a", approved=decision == "approve").request_id == "r"
    with pytest.raises(IncidentContinuationClaimError):
        recover(queue, approval, second)
    current.complete("a")
    assert approval.get_consumption_record("a") == ("completed", decision == "approve")


@pytest.mark.parametrize("journal", ["DELETE", "WAL"])
def test_concurrent_claim_and_recovery_have_exactly_one_winner(tmp_path, journal):
    queue, approval = setup(tmp_path, journal=journal)
    job = queue.claim_next(worker_id="owner")
    barrier = Barrier(2)

    def compete(action):
        local_queue = SqliteIncidentContinuationStore(tmp_path / "queue.db", payload_codec=CODEC)
        local_approval = SqlitePendingApprovalStore(tmp_path / "approval.db")
        barrier.wait(timeout=10)
        try:
            if action == "claim":
                view(local_queue, local_approval, job).claim(approval_id="a", approved=True)
            else:
                recover(local_queue, local_approval, job)
            return action
        except (IncidentContinuationClaimError, ApprovalAlreadyConsumedError):
            return "lost"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(compete, ["claim", "recover"]))
    assert results.count("lost") == 1
    pair = (queue.get("a").status.value, approval.get_consumption_record("a"))
    assert pair == (("claimed", ("claimed", True)) if "claim" in results else ("pending", ("pending", None)))


@pytest.mark.parametrize("method", ["claim", "get_by_approval_id", "complete", "get_consumption_record"])
def test_bound_store_rejects_another_approval(tmp_path, method):
    queue, approval = setup(tmp_path)
    bound = view(queue, approval, queue.claim_next(worker_id="owner"))
    with pytest.raises(IncidentContinuationClaimError):
        if method == "claim":
            bound.claim(approval_id="other", approved=True)
        else:
            getattr(bound, method)("other")
    assert approval.get_consumption_record("a") == ("pending", None)


@pytest.mark.parametrize("approved", [False, None, 1])
def test_decision_cannot_differ_from_durable_invocation(tmp_path, approved):
    queue, approval = setup(tmp_path)
    job = queue.claim_next(worker_id="owner")
    with pytest.raises((IncidentContinuationClaimError, TypeError)):
        queue.claim_approval(approval_id="a", worker_id="owner", expected_attempt_count=1,
                             approved=approved, approval_store=approval)
    assert approval.get_consumption_record("a") == ("pending", None)
    assert queue.get("a") == job


def test_unbound_store_has_no_recovery_or_claim_fallback(tmp_path):
    queue, approval = setup(tmp_path)
    queue.claim_next(worker_id="owner")
    for method in ["claim_approval", "recover_claimed_before_approval"]:
        args = dict(approval_id="a", worker_id="owner", expected_attempt_count=1, approval_store=object())
        if method == "claim_approval":
            args["approved"] = True
        with pytest.raises(TypeError):
            getattr(queue, method)(**args)
    assert approval.get_consumption_record("a") == ("pending", None)


@pytest.mark.asyncio
@pytest.mark.parametrize("commit_happened", [False, True])
async def test_claim_error_never_requeues_based_on_readback(tmp_path, monkeypatch, commit_happened):
    queue, approval = setup(tmp_path)
    original = queue.claim_approval
    responses = []
    async def processor(**kw):
        kw["store"].claim(approval_id="a", approved=True)
        responses.append("response")
    async def notify(**kw):
        pytest.fail("failed claim must not notify")
    def uncertain(**kw):
        if commit_happened:
            original(**kw)
        raise OSError("commit acknowledgement unavailable")
    monkeypatch.setattr(queue, "claim_approval", uncertain)
    worker = IncidentContinuationWorker(IncidentContinuationWorkerDependencies(
        continuation_store=queue, approval_store=approval, workflow_factory=object,
        processor=processor, terminal_notifier=notify,
    ))
    assert await worker.process_next_once() == IncidentContinuationWorkerOutcome.FAILED_CLOSED
    assert queue.get("a").status.value == "failed"
    assert approval.get_consumption_record("a") == (("claimed", True) if commit_happened else ("pending", None))
    assert responses == []
    assert await worker.process_next_once() == IncidentContinuationWorkerOutcome.IDLE


@pytest.mark.asyncio
async def test_replaced_worker_cannot_deliver_response_or_notification(tmp_path):
    queue, approval = setup(tmp_path)
    new_job = []
    async def processor(**kw):
        old = queue.get("a")
        recover(queue, approval, old)
        new_job.append(queue.claim_next(worker_id=old.claimed_by))
        kw["store"].claim(approval_id="a", approved=True)
        pytest.fail("stale worker delivered a workflow response")
    async def notify(**kw):
        pytest.fail("stale worker notified")
    worker = IncidentContinuationWorker(IncidentContinuationWorkerDependencies(
        continuation_store=queue, approval_store=approval, workflow_factory=object,
        processor=processor, terminal_notifier=notify,
    ))
    assert await worker.process_next_once() == IncidentContinuationWorkerOutcome.CLAIM_LOST
    assert queue.get("a") == new_job[0]
    assert approval.get_consumption_record("a") == ("pending", None)


@pytest.mark.asyncio
@pytest.mark.parametrize("stale", [False, True])
@pytest.mark.parametrize("decision", ["approve", "reject"])
async def test_native_maf_processor_uses_attempt_bound_claim(tmp_path, monkeypatch, stale, decision):
    import src.runtime.incident_approval_processor as processor
    from src.runtime.procedure.approval_context import AuthorizedApprovalContext
    from tests.runtime._neutral_incident_case import decision_context, prepare_native_case
    case = await prepare_native_case(tmp_path)
    context = decision_context(case.request, decision)
    queue = SqliteIncidentContinuationStore(tmp_path / "queue.db", payload_codec=ContinuationPayloadCodec(
        invocation_type=AuthorizedApprovalContext,
    ))
    queue.enqueue(context)
    job = queue.claim_next(worker_id="owner")
    bound = view(queue, case.store, job)
    original = processor.recover_safe_communication_context_from_checkpoint
    async def between_restore_and_claim(**kw):
        result = await original(**kw)
        if stale:
            recover(queue, case.store, job)
            queue.claim_next(worker_id="owner")
        return result
    monkeypatch.setattr(processor, "recover_safe_communication_context_from_checkpoint", between_restore_and_claim)
    if stale:
        with pytest.raises(IncidentContinuationClaimError):
            await processor.process_authorized_incident_approval(
                invocation=context, store=bound, workflow=case.factory(), checkpoint_storage=case.storage,
            )
        assert case.store.get_consumption_record(job.approval_id) == ("pending", None)
        assert "azure_operations" not in case.agents.calls
    else:
        result = await processor.process_authorized_incident_approval(
            invocation=context, store=bound, workflow=case.factory(), checkpoint_storage=case.storage,
        )
        assert result.approval_evidence.decision.value == decision
        assert case.store.get_consumption_record(job.approval_id) == ("completed", decision == "approve")


@pytest.mark.parametrize("failure", [False, True])
def test_coordinated_connection_closes_after_commit_or_guard_failure(tmp_path, monkeypatch, failure):
    queue, approval = setup(tmp_path)
    queue.claim_next(worker_id="owner")
    connections = []
    original = sqlite3.connect
    def track(*args, **kw):
        db = original(*args, **kw)
        connections.append(db)
        return db
    monkeypatch.setattr(sqlite3, "connect", track)
    args = dict(approval_id="a", worker_id="owner", expected_attempt_count=2 if failure else 1,
                approved=True, approval_store=approval)
    if failure:
        with pytest.raises(IncidentContinuationClaimError):
            queue.claim_approval(**args)
    else:
        queue.claim_approval(**args)
    assert connections
    for db in connections:
        with pytest.raises(sqlite3.ProgrammingError):
            db.execute("SELECT 1")


@pytest.mark.parametrize("journal", ["DELETE", "WAL"])
def test_recovery_cannot_pass_between_owner_check_and_claim_commit(tmp_path, monkeypatch, journal):
    queue, approval = setup(tmp_path, journal=journal)
    job = queue.claim_next(worker_id="owner")
    checked = Event()
    resume = Event()
    recovery_entered = Event()
    original = sqlite3.connect
    opened = 0

    def connect(*args, **kw):
        nonlocal opened
        db = original(*args, **kw)
        opened += 1
        which = opened
        def trace(sql):
            if which == 1 and sql.startswith("SELECT * FROM approval_side.pending_approvals"):
                checked.set()
                assert resume.wait(timeout=10)
            if which == 2 and sql == "BEGIN IMMEDIATE":
                recovery_entered.set()
        db.set_trace_callback(trace)
        return db

    monkeypatch.setattr(sqlite3, "connect", connect)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claiming = pool.submit(view(queue, approval, job).claim, approval_id="a", approved=True)
        try:
            assert checked.wait(timeout=10)
            recovering = pool.submit(recover, queue, approval, job)
            assert recovery_entered.wait(timeout=10)
            with pytest.raises(TimeoutError):
                recovering.result(timeout=0.05)
        finally:
            resume.set()
        assert claiming.result(timeout=10).approval_id == "a"
        with pytest.raises(IncidentContinuationClaimError):
            recovering.result(timeout=10)
    assert approval.get_consumption_record("a") == ("claimed", True)
    assert queue.get("a").status.value == "claimed"


def test_missing_approval_file_is_not_recreated_by_coordinated_claim(tmp_path):
    queue, approval = setup(tmp_path)
    job = queue.claim_next(worker_id="owner")
    approval.database_path.unlink()
    with pytest.raises(sqlite3.OperationalError):
        view(queue, approval, job).claim(approval_id="a", approved=True)
    assert not approval.database_path.exists()
    assert queue.get("a") == job


def test_special_characters_in_configured_path_are_not_uri_options(tmp_path):
    queue, _ = setup(tmp_path)
    approval = SqlitePendingApprovalStore(tmp_path / "approval # unicode ü.db")
    approval.register(PendingApprovalCorrelation(
        approval_id="a", workflow_id="w", request_id="r", checkpoint_id="c",
    ))
    job = queue.claim_next(worker_id="owner")
    view(queue, approval, job).claim(approval_id="a", approved=True)
    assert approval.get_consumption_record("a") == ("claimed", True)
