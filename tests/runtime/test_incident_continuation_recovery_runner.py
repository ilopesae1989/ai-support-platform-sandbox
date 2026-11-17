import asyncio
import logging
from threading import Event

import pytest

from src.runtime.incident_continuation_recovery import (
    ContinuationRecoveryCandidate as Candidate, IncidentContinuationRecovery,
)
from src.runtime.incident_continuation_recovery_runner import (
    ContinuationRecoveryPolicy as Policy, IncidentContinuationRecoveryRunner as Runner,
)
from src.runtime.incident_continuation_store import IncidentContinuationClaimError
from tests.runtime.test_continuation_approval_claim import setup
from tests.runtime.test_incident_continuation_recovery import aged


class Store:
    def __init__(self):
        self.selections = []
        self.transitions = []
        self.select = lambda **kw: ()
        self.recover = lambda **kw: None

    def list_stale_claims(self, **kw):
        self.selections.append(kw)
        return self.select(**kw)

    def recover_stale_before_approval(self, **kw):
        self.transitions.append(kw)
        return self.recover(**kw)


def runner(store, *, clock=lambda: 500, **policy):
    return Runner(recovery=IncidentContinuationRecovery(continuation_store=store, approval_store=object()),
                  policy=Policy(**(dict(min_claim_age_seconds=100, interval_seconds=1,
                                        batch_size=2, max_batches_per_cycle=2) | policy)), clock=clock)


@pytest.mark.asyncio
async def test_capped_cycles_resume_cursor_and_cutoff_before_starting_new_sweep(caplog):
    caplog.set_level(logging.INFO)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    store = Store()
    times = iter([500, 800])
    def select(**kw):
        number = len(store.selections)
        if number == 1:
            return (Candidate("a", "private-owner", 3, 10), Candidate("b", "private-owner", 3, 10))
        if number == 3:
            loop.call_soon_threadsafe(stop.set)
        return ()
    def reject(**kw):
        raise IncidentContinuationClaimError("private-approval-message")
    store.select, store.recover = select, reject
    task = runner(store, clock=lambda: next(times), max_batches_per_cycle=1)
    await asyncio.wait_for(task.run(stop_event=stop), 5)
    assert store.selections == [dict(stale_before=400, limit=2, after_id=None),
                                dict(stale_before=400, limit=2, after_id="b"),
                                dict(stale_before=700, limit=2, after_id=None)]
    summaries = [r.recovery_cycle for r in caplog.records if hasattr(r, "recovery_cycle")]
    assert [s.reason for s in summaries] == ["cycle_limit", "sweep_complete", "stopped"]
    assert summaries[0].rejected == summaries[0].scanned == 2
    assert "private" not in repr([r.__dict__ for r in caplog.records])


@pytest.mark.asyncio
async def test_pages_within_cycle_have_one_cutoff_and_stop_between_batches():
    stop, store = asyncio.Event(), Store()
    loop = asyncio.get_running_loop()
    def select(**kw):
        if len(store.selections) == 2:
            loop.call_soon_threadsafe(stop.set)
        return (Candidate(str(len(store.selections)), "owner", 1, 10),)
    store.select = select
    task = runner(store, batch_size=1, max_batches_per_cycle=3)
    await asyncio.wait_for(task.run(stop_event=stop), 3)
    assert [s["after_id"] for s in store.selections] == [None, "1"]
    assert {s["stale_before"] for s in store.selections} == {400}
    assert task.last_cycle.requeued == 2 and task.last_cycle.reason == "stopped"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["selection", "transition"])
async def test_uncertainty_latches_without_retry_or_logging_provider_content(failure, caplog):
    store = Store()
    def fail(**kw):
        raise OSError("PRIVATE approval token payload")
    if failure == "selection":
        store.select = fail
    else:
        store.select = lambda **kw: (Candidate("secret-a", "secret-owner", 1, 10), Candidate("secret-b", "secret-owner", 1, 10))
        store.recover = fail
    task = runner(store)
    await asyncio.wait_for(task.run(stop_event=asyncio.Event()), 3)
    assert task.halted and len(store.selections) == 1
    assert len(store.transitions) == (failure == "transition")
    assert task.last_cycle.error_type == "OSError"
    assert task.last_cycle.uncertain == (failure == "transition")
    assert caplog.records[-1].levelno == logging.ERROR
    assert "secret" not in repr(caplog.records[-1].__dict__)
    assert "PRIVATE" not in repr(caplog.records[-1].__dict__)
    with pytest.raises(RuntimeError):
        await task.run(stop_event=asyncio.Event())
    assert len(store.selections) == 1


@pytest.mark.asyncio
async def test_stop_before_start_and_during_interval_causes_no_extra_io():
    stop, store = asyncio.Event(), Store()
    stop.set()
    await runner(store).run(stop_event=stop)
    assert not store.selections
    stop.clear()
    task = runner(store, interval_seconds=86400)
    running = asyncio.create_task(task.run(stop_event=stop))
    try:
        async with asyncio.timeout(3):
            while task.last_cycle is None:
                await asyncio.sleep(0)
        stop.set()
        await asyncio.wait_for(running, 3)
        assert len(store.selections) == 1
    finally:
        stop.set()
        await running


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
@pytest.mark.parametrize("failure", [False, True])
async def test_active_thread_is_drained_before_stop_or_repeated_cancellation(cancel, failure):
    store, stop = Store(), asyncio.Event()
    started, release, committed = asyncio.Event(), Event(), Event()
    loop = asyncio.get_running_loop()
    store.select = lambda **kw: (Candidate("a", "owner", 1, 10),)
    def transition(**kw):
        loop.call_soon_threadsafe(started.set)
        assert release.wait(5), "test did not release batch"
        committed.set()
        if failure:
            raise OSError("commit acknowledgement lost")
    store.recover = transition
    task = runner(store, batch_size=1)
    running = asyncio.create_task(task.run(stop_event=stop))
    try:
        await asyncio.wait_for(started.wait(), 3)
        if cancel:
            running.cancel()
            await asyncio.sleep(0)
            running.cancel()
        else:
            stop.set()
        await asyncio.sleep(0)
        assert not running.done() and not committed.is_set()
        # The event loop remains responsive while the synchronous batch is blocked.
        release.set()
        if cancel:
            with pytest.raises(asyncio.CancelledError):
                await running
        else:
            await running
        assert committed.is_set() and len(store.selections) == len(store.transitions) == 1
        assert task.halted == failure
        assert task.last_cycle.uncertain == failure
        assert task.last_cycle.requeued == (not failure)
    finally:
        release.set()
        if not running.done():
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running


@pytest.mark.asyncio
async def test_same_runner_cannot_run_concurrently():
    store, stop = Store(), asyncio.Event()
    task = runner(store, interval_seconds=86400)
    first = asyncio.create_task(task.run(stop_event=stop))
    try:
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError):
            await task.run(stop_event=stop)
    finally:
        stop.set()
        await first


@pytest.mark.asyncio
@pytest.mark.parametrize("now", [True, -1, float("nan"), float("inf"), "500"])
async def test_invalid_clock_halts_before_persistence(now):
    store = Store()
    task = runner(store, clock=lambda: now)
    await task.run(stop_event=asyncio.Event())
    assert task.halted and task.last_cycle.reason == "clock_error" and not store.selections


@pytest.mark.asyncio
async def test_sqlite_recovery_runner_preserves_hitl_and_does_not_cross_customer(tmp_path):
    pairs = []
    for name in ("customer_a", "customer_b"):
        folder = tmp_path / name
        folder.mkdir()
        queue, approval = setup(folder)
        aged(queue)
        pairs.append((queue, approval))
    queue, approval = pairs[0]
    stop = asyncio.Event()
    task = Runner(recovery=IncidentContinuationRecovery(continuation_store=queue, approval_store=approval),
                  policy=Policy(100, 86400, 10, 1), clock=lambda: 500)
    running = asyncio.create_task(task.run(stop_event=stop))
    try:
        async with asyncio.timeout(3):
            while task.last_cycle is None:
                await asyncio.sleep(0)
        assert task.last_cycle.requeued == 1
        assert queue.get("a").status.value == "pending"
        assert approval.get_consumption_record("a") == ("pending", None)
        assert pairs[1][0].get("a").status.value == "claimed"
        assert pairs[1][1].get_consumption_record("a") == ("pending", None)
    finally:
        stop.set()
        await running
