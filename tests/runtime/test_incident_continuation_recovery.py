"""Offline recovery after a lost process, with real SQLite and no remote effects."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
import sqlite3
import subprocess
import sys
from threading import Barrier

import pytest

from src.persistence.sqlite.incident_continuation_store import SqliteIncidentContinuationStore
from src.runtime.incident_continuation_recovery import (
    ContinuationRecoveryCandidate as Candidate, ContinuationRecoveryOutcome as Outcome,
    IncidentContinuationRecovery,
)
from src.runtime.incident_continuation_store import IncidentContinuationClaimError
from src.runtime.incident_continuation_worker import (
    IncidentContinuationWorker, IncidentContinuationWorkerDependencies, IncidentContinuationWorkerOutcome,
)
from src.runtime.procedure.approval_correlation import PendingApprovalCorrelation
from src.runtime.procedure.approval_store import SqlitePendingApprovalStore, ApprovalAlreadyConsumedError
from src.runtime.procedure.authorized_approval import AuthorizedApprovalInvocation
from tests.runtime.test_continuation_approval_claim import CODEC, setup, view


def update(queue, sql, parameters=()):
    with closing(sqlite3.connect(queue._database_path)) as connection, connection:
        connection.execute(sql, parameters)


def aged(queue, *, worker="owner", timestamp=100):
    original = queue.claim_next(worker_id=worker)
    update(queue, "UPDATE incident_continuation_jobs SET updated_at=? WHERE approval_id=?",
           (timestamp, original.approval_id))
    return queue.list_stale_claims(stale_before=200, limit=100)[0]


def sweep(queue, approval, **extra):
    return IncidentContinuationRecovery(continuation_store=queue, approval_store=approval).run_batch(
        stale_before=200, limit=100, **extra,
    )


@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.parametrize("journal", ["DELETE", "WAL"])
@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_restart_recovers_before_hitl_without_reviving_original_worker(tmp_path, shared, journal, decision):
    queue, approval = setup(tmp_path, shared=shared, journal=journal, decision=decision)
    candidate = aged(queue, worker="reused-owner")
    original = queue.get("a")
    restarted = SqliteIncidentContinuationStore(queue._database_path, payload_codec=CODEC)
    restarted_approval = SqlitePendingApprovalStore(approval.database_path)
    result = sweep(restarted, restarted_approval)
    assert [(r.candidate, r.outcome) for r in result.results] == [(candidate, Outcome.REQUEUED)]
    assert not result.halted and result.next_after_id is None
    assert approval.get_consumption_record("a") == ("pending", None)
    assert queue.get("a").invocation == original.invocation
    second = restarted.claim_next(worker_id="reused-owner")
    assert second.attempt_count == 2
    with pytest.raises(IncidentContinuationClaimError):
        view(queue, approval, original).claim(approval_id="a", approved=decision == "approve")
    view(restarted, restarted_approval, second).claim(approval_id="a", approved=decision == "approve")
    assert approval.get_consumption_record("a") == ("claimed", decision == "approve")


def test_cursor_passes_consumed_and_exhausted_candidates_without_starvation(tmp_path):
    queue, approval = setup(tmp_path)
    aged(queue)
    view(queue, approval, queue.get("a")).claim(approval_id="a", approved=True)
    for name in ("b", "c"):
        approval.register(PendingApprovalCorrelation(
            approval_id=name, workflow_id="w", request_id="r-" + name, checkpoint_id="c-" + name,
        ))
        queue.enqueue(AuthorizedApprovalInvocation(policy_id="p", action={"approval_id": name, "decision": "reject"}))
        queue.claim_next(worker_id="owner")
    update(queue, "UPDATE incident_continuation_jobs SET updated_at=100")
    update(queue, "UPDATE incident_continuation_jobs SET attempt_count=3 WHERE approval_id='b'")
    service = IncidentContinuationRecovery(continuation_store=queue, approval_store=approval)
    first = service.run_batch(stale_before=200, limit=2)
    assert [r.outcome for r in first.results] == [Outcome.REJECTED, Outcome.REJECTED]
    assert first.next_after_id == "b"
    second = service.run_batch(stale_before=first.stale_before, limit=2, after_id=first.next_after_id)
    assert [(r.candidate.approval_id, r.outcome) for r in second.results] == [("c", Outcome.REQUEUED)]
    assert second.next_after_id is None
    assert queue.get("b").attempt_count == 3 and queue.get("b").status.value == "claimed"
    assert approval.get_consumption_record("c") == ("pending", None)


@pytest.mark.parametrize("state,timestamp,expected", [
    ("pending", 100, False), ("completed", 100, False), ("failed", 100, False),
    ("claimed", 199, True), ("claimed", 200, False), ("claimed", 201, False),
])
def test_selector_is_strictly_older_and_claimed_without_decoding_payload(tmp_path, state, timestamp, expected):
    queue, _ = setup(tmp_path)
    aged(queue)
    update(queue, "UPDATE incident_continuation_jobs SET status=?, updated_at=?, payload_json='unreadable'",
           (state, timestamp))
    assert bool(queue.list_stale_claims(stale_before=200, limit=1)) is expected


@pytest.mark.parametrize("change,parameters", [
    ("claimed_by=?", ("other",)), ("attempt_count=?", (2,)),
    ("updated_at=?", (101,)), ("status=?", ("pending",)),
])
def test_changed_snapshot_rejected_without_adopting_fresh_metadata(tmp_path, change, parameters):
    queue, approval = setup(tmp_path)
    candidate = aged(queue)
    update(queue, "UPDATE incident_continuation_jobs SET " + change, parameters)
    with pytest.raises(IncidentContinuationClaimError):
        queue.recover_stale_before_approval(candidate=candidate, stale_before=200, approval_store=approval)
    assert approval.get_consumption_record("a") == ("pending", None)


@pytest.mark.parametrize("record", [("claimed", 1), ("completed", 0), ("pending", 1), None])
def test_consumed_inconsistent_or_missing_approval_never_recovers(tmp_path, record):
    queue, approval = setup(tmp_path)
    candidate = aged(queue)
    with closing(sqlite3.connect(approval.database_path)) as connection, connection:
        if record is None:
            connection.execute("DELETE FROM pending_approvals")
        else:
            connection.execute("UPDATE pending_approvals SET consumption_status=?, approved_decision=?", record)
    assert sweep(queue, approval).results[0].outcome == Outcome.REJECTED
    assert queue.list_stale_claims(stale_before=200, limit=1) == (candidate,)


@pytest.mark.parametrize("journal", ["DELETE", "WAL"])
@pytest.mark.parametrize("competitor", ["claim", "recover"])
def test_concurrent_recovery_and_competitor_have_one_winner(tmp_path, journal, competitor):
    queue, approval = setup(tmp_path, journal=journal)
    candidate = aged(queue)
    original = queue.get("a")
    barrier = Barrier(2)

    def compete(action):
        local = SqliteIncidentContinuationStore(queue._database_path, payload_codec=CODEC)
        local_approval = SqlitePendingApprovalStore(approval.database_path)
        barrier.wait(timeout=10)
        try:
            if action == "claim":
                view(local, local_approval, original).claim(approval_id="a", approved=True)
            else:
                local.recover_stale_before_approval(candidate=candidate, stale_before=200, approval_store=local_approval)
            return "won"
        except (IncidentContinuationClaimError, ApprovalAlreadyConsumedError):
            return "lost"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(compete, ("recover", competitor)))
    assert sorted(results) == ["lost", "won"]
    pair = (queue.get("a").status.value, approval.get_consumption_record("a"))
    assert pair in [("pending", ("pending", None)), ("claimed", ("claimed", True))]


@pytest.mark.asyncio
async def test_delayed_live_worker_cannot_respond_or_notify_after_sweep(tmp_path):
    queue, approval = setup(tmp_path)
    replacement = []
    async def processor(**kwargs):
        update(queue, "UPDATE incident_continuation_jobs SET updated_at=100")
        assert sweep(queue, approval).results[0].outcome == Outcome.REQUEUED
        replacement.append(queue.claim_next(worker_id=queue_owner))
        kwargs["store"].claim(approval_id="a", approved=True)
        pytest.fail("A replaced attempt delivered a workflow response.")
    async def notify(**kwargs):
        pytest.fail("A replaced attempt notified the channel.")
    queue_owner = "same-owner"
    worker = IncidentContinuationWorker(IncidentContinuationWorkerDependencies(
        continuation_store=queue, approval_store=approval, workflow_factory=object,
        processor=processor, terminal_notifier=notify, worker_id=queue_owner,
    ))
    assert await worker.process_next_once() == IncidentContinuationWorkerOutcome.CLAIM_LOST
    assert queue.get("a") == replacement[0]
    assert approval.get_consumption_record("a") == ("pending", None)


@pytest.mark.parametrize("commit_happened", [False, True])
def test_uncertain_recovery_stops_without_readback_retry_or_later_mutation(tmp_path, monkeypatch, commit_happened):
    queue, approval = setup(tmp_path)
    first = aged(queue)
    candidates = (first, replace(first, approval_id="b"), replace(first, approval_id="c"))
    original = queue.recover_stale_before_approval
    calls = []
    def uncertain(**kwargs):
        calls.append(kwargs["candidate"].approval_id)
        if commit_happened:
            original(**kwargs)
        raise OSError("sensitive DB details must not be copied into the result")
    monkeypatch.setattr(queue, "list_stale_claims", lambda **kw: candidates)
    monkeypatch.setattr(queue, "recover_stale_before_approval", uncertain)
    monkeypatch.setattr(approval, "get_consumption_record", lambda *a: pytest.fail("No readback permission."))
    result = sweep(queue, approval)
    assert calls == ["a"] and result.halted and result.next_after_id is None
    assert len(result.results) == 1
    assert result.results[0].outcome == Outcome.UNCERTAIN
    assert result.results[0].error_type == "OSError" and "sensitive" not in repr(result)
    assert queue.get("a").status.value == ("pending" if commit_happened else "claimed")


@pytest.mark.parametrize("field,value", [
    ("stale_before", True), ("stale_before", float("nan")), ("stale_before", float("inf")),
    ("stale_before", -1), ("limit", 0), ("limit", 101), ("limit", True),
    ("limit", 1.5), ("after_id", ""), ("after_id", " a"),
])
def test_invalid_batch_input_never_opens_persistence(field, value):
    service = IncidentContinuationRecovery(continuation_store=object(), approval_store=object())
    kwargs = dict(stale_before=200, limit=2, after_id=None)
    kwargs[field] = value
    with pytest.raises(ValueError):
        service.run_batch(**kwargs)


@pytest.mark.parametrize("page_kind", ["duplicate", "oversized", "too_recent", "wrong_type", "cursor"])
def test_invalid_adapter_page_rejected_before_any_mutation(page_kind):
    candidate = Candidate("a", "owner", 1, 100)
    pages = {"duplicate": (candidate, candidate), "oversized": (candidate,) * 3,
             "too_recent": (candidate, replace(candidate, approval_id="b", updated_at=200)),
             "wrong_type": (candidate, object()), "cursor": (replace(candidate, approval_id="previous"),)}
    class Store:
        def list_stale_claims(self, **kw):
            return pages[page_kind]
        def recover_stale_before_approval(self, **kw):
            pytest.fail("Must validate the complete page before mutating.")
    service = IncidentContinuationRecovery(continuation_store=Store(), approval_store=object())
    with pytest.raises((ValueError, TypeError)):
        service.run_batch(stale_before=200, limit=2, after_id="previous")


def test_partial_results_preserved_and_no_cursor_after_unknown_error():
    candidates = tuple(Candidate(name, "owner", 1, 100) for name in "abcd")
    calls = []
    class Store:
        def list_stale_claims(self, **kw):
            return candidates
        def recover_stale_before_approval(self, *, candidate, **kw):
            calls.append(candidate.approval_id)
            if candidate.approval_id == "b":
                raise IncidentContinuationClaimError()
            if candidate.approval_id == "c":
                raise RuntimeError()
    result = IncidentContinuationRecovery(continuation_store=Store(), approval_store=object()).run_batch(
        stale_before=200, limit=4,
    )
    assert calls == ["a", "b", "c"]
    assert [r.outcome for r in result.results] == [Outcome.REQUEUED, Outcome.REJECTED, Outcome.UNCERTAIN]
    assert result.halted and result.next_after_id is None


@pytest.mark.parametrize("missing", ["queue", "approval", None])
def test_scan_and_recovery_close_connections_without_gc_and_do_not_create_missing_files(tmp_path, monkeypatch, missing):
    queue, approval = setup(tmp_path)
    candidate = aged(queue)
    removed = queue._database_path if missing == "queue" else approval.database_path
    if missing:
        removed.unlink()
    original = sqlite3.connect
    connections = []
    def tracked(*args, **kwargs):
        connection = original(*args, **kwargs)
        connections.append(connection)
        return connection
    monkeypatch.setattr(sqlite3, "connect", tracked)
    if missing == "queue":
        with pytest.raises(sqlite3.OperationalError):
            queue.list_stale_claims(stale_before=200, limit=1)
    else:
        assert queue.list_stale_claims(stale_before=200, limit=1) == (candidate,)
    if missing:
        with pytest.raises(sqlite3.OperationalError):
            queue.recover_stale_before_approval(candidate=candidate, stale_before=200, approval_store=approval)
        assert not removed.exists()
    else:
        queue.recover_stale_before_approval(candidate=candidate, stale_before=200, approval_store=approval)
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")


def test_recovery_rejects_uncoordinated_sqlite_store(tmp_path):
    queue, _ = setup(tmp_path)
    candidate = aged(queue)
    with pytest.raises(TypeError):
        queue.recover_stale_before_approval(candidate=candidate, stale_before=200, approval_store=object())
    assert queue.list_stale_claims(stale_before=200, limit=1) == (candidate,)


def test_committed_claim_survives_abrupt_process_exit_and_can_be_recovered(tmp_path):
    queue, approval = setup(tmp_path)
    script = """
import os, sys
from src.persistence.sqlite.incident_continuation_store import SqliteIncidentContinuationStore
from src.runtime.incident_continuation_codec import ContinuationPayloadCodec
from src.runtime.procedure.authorized_approval import AuthorizedApprovalInvocation
queue = SqliteIncidentContinuationStore(sys.argv[1], payload_codec=ContinuationPayloadCodec(
    invocation_type=AuthorizedApprovalInvocation))
assert queue.claim_next(worker_id='lost-process').attempt_count == 1
os._exit(73)
"""
    completed = subprocess.run([sys.executable, "-B", "-c", script, str(queue._database_path)],
                               capture_output=True, text=True, timeout=30)
    assert completed.returncode == 73, completed.stderr
    persisted = queue.get("a")
    assert persisted.status.value == "claimed" and persisted.claimed_by == "lost-process"
    result = IncidentContinuationRecovery(continuation_store=queue, approval_store=approval).run_batch(
        stale_before=persisted.updated_at + 1, limit=1,
    )
    assert result.results[0].outcome == Outcome.REQUEUED
    assert approval.get_consumption_record("a") == ("pending", None)
    assert queue.claim_next(worker_id="replacement").attempt_count == 2


def test_repeated_sweeps_preserve_attempt_budget_and_stop_on_third_claim(tmp_path):
    queue, approval = setup(tmp_path)
    for attempt in (1, 2, 3):
        candidate = aged(queue)
        assert candidate.attempt_count == attempt
        expected = Outcome.REQUEUED if attempt < 3 else Outcome.REJECTED
        assert sweep(queue, approval).results[0].outcome == expected
    assert queue.get("a").status.value == "claimed"
    assert queue.get("a").attempt_count == 3
    assert approval.get_consumption_record("a") == ("pending", None)


@pytest.mark.parametrize("commit_happened", [False, True])
def test_sqlite_commit_failure_rolls_back_when_possible_and_stops_batch(tmp_path, monkeypatch, commit_happened):
    queue, approval = setup(tmp_path)
    aged(queue)
    original = sqlite3.connect
    connections = []
    class FailingCommit(sqlite3.Connection):
        def commit(self):
            if commit_happened:
                super().commit()
            raise OSError("lost commit acknowledgement")
    def connect(*args, **kwargs):
        connection = original(*args, **kwargs, factory=FailingCommit)
        connections.append(connection)
        return connection
    with monkeypatch.context() as scoped:
        scoped.setattr(sqlite3, "connect", connect)
        result = sweep(queue, approval)
    assert result.halted and result.results[0].outcome == Outcome.UNCERTAIN
    assert queue.get("a").status.value == ("pending" if commit_happened else "claimed")
    assert approval.get_consumption_record("a") == ("pending", None)
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")
