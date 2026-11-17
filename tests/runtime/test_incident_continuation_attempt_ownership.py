"""Queue generation fences; no claim of remote/HITL lease recovery."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import pytest

from src.persistence.azure_sql.incident_continuation_store import AzureSqlIncidentContinuationStore
from src.persistence.sqlite.incident_continuation_store import SqliteIncidentContinuationStore
from src.runtime.incident_continuation_codec import ContinuationPayloadCodec
from src.runtime.incident_continuation_store import IncidentContinuationClaimError
from src.runtime.incident_continuation_worker import (
    IncidentContinuationWorker, IncidentContinuationWorkerDependencies,
    IncidentContinuationWorkerOutcome,
)
from src.runtime.procedure.approval_correlation import PendingApprovalCorrelation
from src.runtime.procedure.approval_store import SqlitePendingApprovalStore
from src.runtime.procedure.authorized_approval import AuthorizedApprovalInvocation


CODEC = ContinuationPayloadCodec(invocation_type=AuthorizedApprovalInvocation)
APPROVAL_ID = "approval-attempt-test"
OWNER = "same-worker-across-attempts"


def stores(tmp_path):
    queue = SqliteIncidentContinuationStore(tmp_path / "queue.db", payload_codec=CODEC)
    approvals = SqlitePendingApprovalStore(tmp_path / "approvals.db")
    approvals.register(PendingApprovalCorrelation(
        approval_id=APPROVAL_ID, workflow_id="workflow", request_id="request",
        checkpoint_id="checkpoint",
    ))
    queue.enqueue(AuthorizedApprovalInvocation(
        policy_id="policy", action={"approval_id": APPROVAL_ID, "decision": "approve"},
    ))
    return queue, approvals


def mutate(queue, method, attempt, *, approvals, owner=OWNER):
    kwargs = dict(approval_id=APPROVAL_ID, worker_id=owner,
                  expected_attempt_count=attempt)
    if method == "fail":
        kwargs["error"] = "synthetic"
    if method == "recover_claimed_before_approval":
        kwargs["approval_store"] = approvals
    return getattr(queue, method)(**kwargs)


def reclaim(queue, approvals):
    first = queue.claim_next(worker_id=OWNER)
    mutate(queue, "recover_claimed_before_approval", first.attempt_count, approvals=approvals)
    second = queue.claim_next(worker_id=OWNER)
    assert (first.attempt_count, second.attempt_count) == (1, 2)
    return first, second


@pytest.mark.parametrize("method", ["complete", "fail", "recover_claimed_before_approval"])
def test_same_owner_stale_attempt_cannot_mutate_reclaimed_job_after_reopen(tmp_path, method):
    queue, approvals = stores(tmp_path)
    first, second = reclaim(queue, approvals)
    restarted = SqliteIncidentContinuationStore(tmp_path / "queue.db", payload_codec=CODEC)
    with pytest.raises(IncidentContinuationClaimError):
        mutate(restarted, method, first.attempt_count, approvals=approvals)
    assert restarted.get(APPROVAL_ID) == second
    assert approvals.get_consumption_record(APPROVAL_ID) == ("pending", None)
    current = mutate(restarted, method, second.attempt_count, approvals=approvals)
    assert current.status.value == {
        "complete": "completed", "fail": "failed", "recover_claimed_before_approval": "pending",
    }[method]
    assert current.attempt_count == 2
    assert current.invocation == first.invocation


@pytest.mark.parametrize("method", ["complete", "fail", "recover_claimed_before_approval"])
def test_current_generation_does_not_authorize_another_owner(tmp_path, method):
    queue, approvals = stores(tmp_path)
    claimed = queue.claim_next(worker_id=OWNER)
    with pytest.raises(IncidentContinuationClaimError):
        mutate(queue, method, claimed.attempt_count, approvals=approvals, owner="other")
    assert queue.get(APPROVAL_ID) == claimed


def test_two_terminal_transitions_of_one_attempt_have_only_one_winner(tmp_path):
    queue, approvals = stores(tmp_path)
    claimed = queue.claim_next(worker_id=OWNER)
    barrier = Barrier(2)

    def transition(method):
        local = SqliteIncidentContinuationStore(tmp_path / "queue.db", payload_codec=CODEC)
        barrier.wait(timeout=10)
        try:
            return mutate(local, method, claimed.attempt_count, approvals=approvals).status.value
        except IncidentContinuationClaimError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(transition, ("complete", "fail")))
    assert results.count("conflict") == 1
    final = queue.get(APPROVAL_ID)
    assert final.status.value in {"completed", "failed"}
    assert final.status.value in results
    assert final.attempt_count == 1


def test_stale_and_current_attempt_race_cannot_overwrite_current_result(tmp_path):
    queue, approvals = stores(tmp_path)
    first, second = reclaim(queue, approvals)
    barrier = Barrier(2)

    def transition(attempt):
        local = SqliteIncidentContinuationStore(tmp_path / "queue.db", payload_codec=CODEC)
        barrier.wait(timeout=10)
        try:
            mutate(local, "fail" if attempt == 2 else "complete", attempt, approvals=approvals)
            return "changed"
        except IncidentContinuationClaimError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(transition, (first.attempt_count, second.attempt_count)))
    assert results == ["conflict", "changed"]
    assert queue.get(APPROVAL_ID).status.value == "failed"


def test_store_enforces_recovery_budget_without_worker_and_preserves_consumption(tmp_path):
    queue, approvals = stores(tmp_path)
    for attempt in (1, 2):
        claimed = queue.claim_next(worker_id=OWNER)
        assert claimed.attempt_count == attempt
        mutate(queue, "recover_claimed_before_approval", attempt, approvals=approvals)
    third = queue.claim_next(worker_id=OWNER)
    with pytest.raises(IncidentContinuationClaimError):
        mutate(queue, "recover_claimed_before_approval", 3, approvals=approvals)
    assert queue.get(APPROVAL_ID) == third
    assert approvals.get_consumption_record(APPROVAL_ID) == ("pending", None)
    assert mutate(queue, "fail", 3, approvals=approvals).status.value == "failed"


@pytest.mark.parametrize("backend", ["sqlite", "azure_sql"])
@pytest.mark.parametrize("attempt", [None, True, False, 0, -1, 1.0, "1"])
def test_invalid_generation_is_rejected_before_any_database_or_approval_access(
    tmp_path, monkeypatch, backend, attempt,
):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid generation must not access persistence")

    if backend == "sqlite":
        queue = SqliteIncidentContinuationStore(tmp_path / "queue.db", payload_codec=CODEC)
        monkeypatch.setattr(queue, "_connect", forbidden)
    else:
        queue = AzureSqlIncidentContinuationStore(connection_factory=forbidden, payload_codec=CODEC)
    approvals = SimpleNamespace(get_consumption_record=forbidden)
    for method in ("complete", "fail", "recover_claimed_before_approval"):
        with pytest.raises(ValueError, match="expected_attempt_count"):
            mutate(queue, method, attempt, approvals=approvals)


def test_missing_generation_has_no_compatibility_fallback(tmp_path):
    queue, approvals = stores(tmp_path)
    claimed = queue.claim_next(worker_id=OWNER)
    for method in ("complete", "fail", "recover_claimed_before_approval"):
        kwargs = dict(approval_id=APPROVAL_ID, worker_id=OWNER)
        if method == "fail":
            kwargs["error"] = "synthetic"
        if method == "recover_claimed_before_approval":
            kwargs["approval_store"] = approvals
        with pytest.raises(TypeError, match="expected_attempt_count"):
            getattr(queue, method)(**kwargs)
    assert queue.get(APPROVAL_ID) == claimed


@pytest.mark.asyncio
@pytest.mark.parametrize("approval_state", ["pending", "claimed", "unavailable"])
async def test_old_worker_error_does_not_fail_or_requeue_the_new_attempt(
    tmp_path, monkeypatch, approval_state,
):
    queue, approvals = stores(tmp_path)
    newer = []
    notices = []

    async def processor(**kwargs):
        job = queue.get(APPROVAL_ID)
        mutate(queue, "recover_claimed_before_approval", job.attempt_count, approvals=approvals)
        newer.append(queue.claim_next(worker_id=OWNER))
        if approval_state == "claimed":
            approvals.claim(approval_id=APPROVAL_ID, approved=True)
        elif approval_state == "unavailable":
            def unavailable(*args):
                raise OSError("synthetic read failure")
            monkeypatch.setattr(approvals, "get_consumption_record", unavailable)
        raise RuntimeError("old attempt resumes after replacement")

    async def notifier(**kwargs):
        notices.append(kwargs)

    worker = IncidentContinuationWorker(IncidentContinuationWorkerDependencies(
        continuation_store=queue, approval_store=approvals, workflow_factory=object,
        processor=processor, terminal_notifier=notifier, worker_id=OWNER,
    ))
    assert await worker.process_next_once() == IncidentContinuationWorkerOutcome.CLAIM_LOST
    assert queue.get(APPROVAL_ID) == newer[0]
    assert newer[0].attempt_count == 2
    assert notices == []
    assert await worker.process_next_once() == IncidentContinuationWorkerOutcome.IDLE


@pytest.mark.asyncio
async def test_worker_uses_claimed_generation_after_a_previous_retry(tmp_path):
    queue, approvals = stores(tmp_path)
    first = queue.claim_next(worker_id=OWNER)
    mutate(queue, "recover_claimed_before_approval", first.attempt_count, approvals=approvals)
    events = []

    async def processor(**kwargs):
        assert queue.get(APPROVAL_ID).attempt_count == 2
        kwargs["store"].claim(approval_id=APPROVAL_ID, approved=True)
        kwargs["store"].complete(APPROVAL_ID)
        events.append("processed")
        return object()

    async def notifier(**kwargs):
        events.append("notified")

    worker = IncidentContinuationWorker(IncidentContinuationWorkerDependencies(
        continuation_store=queue, approval_store=approvals, workflow_factory=object,
        processor=processor, terminal_notifier=notifier, worker_id=OWNER,
    ))
    assert await worker.process_next_once() == IncidentContinuationWorkerOutcome.COMPLETED
    assert events == ["processed", "notified"]
    assert queue.get(APPROVAL_ID).attempt_count == 2
    assert approvals.get_consumption_record(APPROVAL_ID) == ("completed", True)


def test_default_worker_owner_is_unique_and_stable_for_each_instance():
    kwargs = dict(continuation_store=object(), approval_store=object(),
                  workflow_factory=object, processor=object(), terminal_notifier=object())
    first = IncidentContinuationWorkerDependencies(**kwargs)
    second = IncidentContinuationWorkerDependencies(**kwargs)
    assert first.worker_id != second.worker_id
    assert first.worker_id == first.worker_id.strip()
    assert 0 < len(first.worker_id) <= 256
    assert IncidentContinuationWorker(first)._dependencies.worker_id == first.worker_id


@pytest.mark.asyncio
async def test_cancellation_keeps_claimed_job_and_does_not_enable_restart_retry(tmp_path):
    import asyncio
    queue, approvals = stores(tmp_path)
    notifications = []

    async def cancelled(**kwargs):
        raise asyncio.CancelledError

    async def notifier(**kwargs):
        notifications.append(kwargs)

    worker = IncidentContinuationWorker(IncidentContinuationWorkerDependencies(
        continuation_store=queue, approval_store=approvals, workflow_factory=object,
        processor=cancelled, terminal_notifier=notifier,
    ))
    with pytest.raises(asyncio.CancelledError):
        await worker.process_next_once()
    job = queue.get(APPROVAL_ID)
    assert (job.status.value, job.attempt_count) == ("claimed", 1)
    assert notifications == []
    assert approvals.get_consumption_record(APPROVAL_ID) == ("pending", None)
    restarted = IncidentContinuationWorker(IncidentContinuationWorkerDependencies(
        continuation_store=queue, approval_store=approvals, workflow_factory=object,
        processor=cancelled, terminal_notifier=notifier,
    ))
    assert await restarted.process_next_once() == IncidentContinuationWorkerOutcome.IDLE


def test_pre_p4_claimed_row_keeps_payload_and_attempt_and_can_be_completed(tmp_path):
    import sqlite3
    from src.channels.teams.continuation_payload import TEAMS_CONTINUATION_CODEC
    payload = (Path(__file__).parents[1] / "fixtures/continuations/teams_before_e3_p2.json").read_text(
        encoding="utf-8",
    ).strip()
    path = tmp_path / "historical.db"
    SqliteIncidentContinuationStore(path, payload_codec=TEAMS_CONTINUATION_CODEC)
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO incident_continuation_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   ("approval-fixture-v1", payload, "claimed", 2, "historical-owner", None, 1.0, 2.0))
    reopened = SqliteIncidentContinuationStore(path, payload_codec=TEAMS_CONTINUATION_CODEC)
    job = reopened.get("approval-fixture-v1")
    result = reopened.complete(approval_id=job.approval_id, worker_id=job.claimed_by,
                              expected_attempt_count=job.attempt_count)
    assert result.status.value == "completed"
    assert TEAMS_CONTINUATION_CODEC.encode(result.invocation) == payload
    assert result.attempt_count == 2
