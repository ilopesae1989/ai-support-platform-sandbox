import pytest

from src.persistence.execution_inventory import sqlite_inventory_page
from tests.workflows.incident_resolution.test_admitted_execution_checkpoint import configured, pending, setup, worker
from tests.workflows.incident_resolution.test_incident_workflow_azure_operations import SingleStepAzureWorkflowFakeFoundryAgents


@pytest.mark.asyncio
@pytest.mark.parametrize("stop", ["before_commit", "after_commit", None])
async def test_admitted_resolution_after_reopen(tmp_path, monkeypatch, stop):
    state = setup(tmp_path)
    agents = SingleStepAzureWorkflowFakeFoundryAgents()
    agents.deployment_fingerprint = state.case.agents.deployment_fingerprint
    state.case.agents = agents
    state.factory = configured(state.case, state.queue, state.approvals, state.storage)
    request, _ = await pending(state, decision="approve")
    active, notifications = worker(state)
    class SimulatedProcessLoss(BaseException):
        pass

    complete = state.queue.complete_resolution
    arguments = {}

    def finish(**kwargs):
        arguments.update(kwargs)
        if stop == "before_commit":
            raise SimulatedProcessLoss()
        job = complete(**kwargs)
        if stop == "after_commit":
            raise SimulatedProcessLoss()
        return job

    monkeypatch.setattr(state.queue, "complete_resolution", finish)
    if stop:
        with pytest.raises(SimulatedProcessLoss):
            await active.process_next_once()
    else:
        assert (await active.process_next_once()).value == "completed"
    result = notifications[0].workflow_result
    assert result.workflow_status == "resolved"
    row, = sqlite_inventory_page(database=state.path, checkpoints=tmp_path / "checkpoints",
                                 consumer=state.case.affinity)["executions"]
    assert row["execution_id"] == result.workflow_id == state.admitted.execution_id
    assert state.approvals.get_consumption_record(request.data.approval_id) == ("completed", True)
    if stop == "before_commit":
        assert row["resolution_receipt"]["status"] == "absent"
        assert row["observed_state"] == "unresolved"
        assert row["candidate_jobs"] == {"claimed": 1}
        return
    assert row["observed_state"] == "terminal_checkpoint"
    assert row["resolution_receipt"]["notification_delivery"] == "unconfirmed"
    assert complete(**arguments).status.value == "completed"
    changed = dict(arguments, outcome=result.model_copy(update={"correlation_id": "changed"}))
    with pytest.raises(ValueError, match="conflicts"):
        complete(**changed)
    assert (await active.process_next_once()).value == "idle"
    assert len(notifications) == 1 and agents.calls.count("azure_operations") == 1
    assert row["rejection_receipt"]["status"] == "absent"
    assert row["resolution_receipt"]["status"] == "recorded"
