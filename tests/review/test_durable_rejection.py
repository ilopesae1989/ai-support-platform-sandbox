from contextlib import closing
import sqlite3

import pytest

from src.persistence.sqlite.execution_store import SqliteExecutionStore
from src.runtime.procedure.workflow import ApprovalOutcome
from tests.runtime.test_incident_execution_queue import CODEC
from tests.workflows.incident_resolution.test_admitted_execution_checkpoint import setup, pending, worker


@pytest.mark.asyncio
async def test_rejection_survives_restart_and_confirms_only_original_attempt(tmp_path):
    state = setup(tmp_path)
    req, _ = await pending(state)
    ident = state.admitted.execution_id
    def reopen():
        return SqliteExecutionStore(state.path, execution_affinity=state.case.affinity,
                                   payload_codec=CODEC, approval_store=state.approvals)
    assert reopen().rejection_closure(ident) is None
    active, _ = worker(state)
    assert (await active.process_next_once()).value == "completed"
    queue = reopen()
    assert queue.rejection_closure(ident) == req.data.approval_id
    with closing(sqlite3.connect(state.path)) as db:
        owner, attempt = db.execute("SELECT worker_id, attempt FROM incident_rejection_closures").fetchone()
    args = dict(approval_id=req.data.approval_id, expected_attempt_count=attempt,
                outcome=ApprovalOutcome(workflow_id=ident, approved=False, status="blocked"))
    assert queue.complete_rejection(worker_id=owner, **args).status.value == "completed"
    with pytest.raises(ValueError, match="conflicts"):
        queue.complete_rejection(worker_id="stale-worker", **args)


@pytest.mark.asyncio
async def test_failed_receipt_insert_rolls_back_queue_completion(tmp_path):
    state = setup(tmp_path)
    req, _ = await pending(state)
    with closing(sqlite3.connect(state.path)) as db:
        db.execute("CREATE TRIGGER interrupt_close BEFORE INSERT ON incident_rejection_closures "
                   "BEGIN SELECT RAISE(ABORT, 'interrupt'); END")
    active, _ = worker(state)
    await active.process_next_once()
    assert state.queue.rejection_closure(state.admitted.execution_id) is None
    assert state.queue.get(req.data.approval_id).status.value != "completed"
    assert state.approvals.get_consumption_record(req.data.approval_id) == ("completed", False)


@pytest.mark.asyncio
@pytest.mark.parametrize("after_commit", [False, True])
async def test_lost_worker_at_transaction_boundary(tmp_path, monkeypatch, after_commit):
    state = setup(tmp_path)
    req, _ = await pending(state)
    class WorkerStopped(BaseException):
        pass
    finish = state.queue.complete_rejection
    def interrupted(**kwargs):
        if after_commit:
            finish(**kwargs)
        raise WorkerStopped()
    monkeypatch.setattr(state.queue, "complete_rejection", interrupted)
    active, _ = worker(state)
    with pytest.raises(WorkerStopped):
        await active.process_next_once()
    reopened = SqliteExecutionStore(state.path, execution_affinity=state.case.affinity,
                                   payload_codec=CODEC, approval_store=state.approvals)
    assert reopened.rejection_closure(state.admitted.execution_id) == (req.data.approval_id if after_commit else None)
    assert reopened.get(req.data.approval_id).status.value == ("completed" if after_commit else "claimed")
    assert state.approvals.get_consumption_record(req.data.approval_id) == ("completed", False)
