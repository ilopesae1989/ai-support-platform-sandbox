import json
from dataclasses import replace

import pytest

from src.runtime.incident_execution import MANUAL_ANALYSIS_REASON_KEY

from src.persistence.execution_inventory import sqlite_inventory_page
from src.workflows.incident_resolution.models import ManualAnalysisRequest
from tests.workflows.incident_resolution.test_admitted_execution_checkpoint import setup
from tests.workflows.incident_resolution.test_routing_executors import create_context


@pytest.mark.asyncio
@pytest.mark.parametrize(("route", "reason"), [
    ("manual_analysis", "no_procedure"),
    ("human_escalation", "human_escalation_required"),
])
async def test_manual_output_and_reopened_inventory(tmp_path, monkeypatch, route, reason):
    state = setup(tmp_path)

    async def triage(*args, **kwargs):
        return create_context(procedure_match="none", execution_eligible=False,
                              recommended_next_step=route, procedure_found=False).triage

    monkeypatch.setattr(state.case.agents, "run_alert_triage", triage)
    events = [event async for event in state.factory().run(
        state.admitted, checkpoint_storage=state.storage, stream=True)]
    output, = [event.data for event in events if event.type == "output"]
    assert isinstance(output, ManualAnalysisRequest)
    assert (output.alert_id, output.reason) == (state.admitted.alert.alert_id, reason)
    assert not any(event.type == "request_info" for event in events)
    row, = sqlite_inventory_page(database=state.path, checkpoints=tmp_path / "checkpoints",
                                 consumer=state.case.affinity)["executions"]
    assert row["execution_id"] == state.admitted.execution_id
    assert row["observed_state"] == "manual_analysis_requested"
    assert row["manual_analysis_reason"] == reason
    report = sqlite_inventory_page(database=state.path, checkpoints=tmp_path / "checkpoints",
                                   consumer=state.case.affinity)
    assert report["page_drain_blockers"] == [
        {"execution_id": row["execution_id"], "reasons": ["manual_handoff_unconfirmed"]}]
    other = replace(state.case.affinity, installation_id="customer-b")
    foreign = sqlite_inventory_page(database=state.path, checkpoints=tmp_path / "checkpoints", consumer=other)
    assert foreign["executions"] == foreign["page_drain_blockers"] == []
    assert row["approvals"] == row["candidate_jobs"] == {}
    assert row["resolution_receipt"]["status"] == row["rejection_receipt"]["status"] == "absent"

    # Model a historical checkpoint and then a malformed one on the same admitted chain.
    for path in (tmp_path / "checkpoints").glob("*.json"):
        doc = json.loads(path.read_text())
        if MANUAL_ANALYSIS_REASON_KEY in doc["state"]:
            break
    else:
        pytest.fail("Missing terminal checkpoint marker")
    for replacement, expected in [(None, "end_unconfirmed"), ("invalid", "unresolved")]:
        doc["state"].pop(MANUAL_ANALYSIS_REASON_KEY, None)
        if replacement is not None:
            doc["state"][MANUAL_ANALYSIS_REASON_KEY] = replacement
        path.write_text(json.dumps(doc), encoding="utf-8")
        historical, = sqlite_inventory_page(database=state.path, checkpoints=tmp_path / "checkpoints",
                                             consumer=state.case.affinity)["executions"]
        assert historical["observed_state"] == expected
        assert historical["manual_analysis_reason"] is None
