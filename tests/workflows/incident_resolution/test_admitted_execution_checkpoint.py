"""Native MAF admission/queue/checkpoint integration with synthetic agents."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from agent_framework import FileCheckpointStorage
from agent_framework.exceptions import WorkflowCheckpointException

from src.persistence.checkpoint_codec import WorkflowCheckpointCodec
from src.persistence.sqlite.execution_store import SqliteExecutionStore
from src.runtime.incident_execution import EXECUTION_ID_STATE_KEY
from src.runtime.incident_approval_processor import process_authorized_incident_approval
from src.runtime.incident_continuation_worker import IncidentContinuationWorker, IncidentContinuationWorkerDependencies
from src.runtime.procedure.approval_correlation import build_pending_approval_correlation
from src.runtime.procedure.approval_store import SqlitePendingApprovalStore
from src.workflows.incident_resolution.composition import IncidentWorkflowOptions, build_incident_workflow_factory
from src.workflows.incident_resolution.checkpoint_storage import (
    incident_checkpoint_allowed_types, admitted_incident_checkpoint_allowed_types,
)
from src.workflows.incident_resolution.operation_dispatch_ledger import InMemoryOperationDispatchLedger
from src.workflows.incident_resolution.wait_recheck_consumption_ledger import InMemoryWaitRecheckConsumptionLedger
from src.workflows.incident_resolution.workflow_input import IncidentWorkflowInput, admit_incident_workflow_input
from tests.runtime._neutral_incident_case import decision_context
from tests.runtime.test_incident_execution_queue import CODEC, snapshot
from tests.workflows.incident_resolution.test_execution_affinity_checkpoint import candidate, graph
from tests.workflows.incident_resolution.test_incident_workflow_azure_operations import create_alert


def configured(case, queue, approvals, storage):
    return build_incident_workflow_factory(approval_store=approvals, checkpoint_storage=storage,
        operation_dispatch_ledger=InMemoryOperationDispatchLedger(),
        wait_recheck_consumption_ledger=InMemoryWaitRecheckConsumptionLedger(),
        options=IncidentWorkflowOptions(agents=case.agents, execution_affinity=case.affinity,
            procedure_configuration=case.procedures, execution_store=queue))


def setup(tmp_path):
    case = candidate(tmp_path)
    approvals = SqlitePendingApprovalStore(tmp_path / "state.db")
    queue = SqliteExecutionStore(tmp_path / "state.db", execution_affinity=case.affinity,
                                payload_codec=CODEC, approval_store=approvals)
    storage = FileCheckpointStorage(tmp_path / "checkpoints",
        allowed_checkpoint_types=admitted_incident_checkpoint_allowed_types())
    factory = configured(case, queue, approvals, storage)
    admitted = admit_incident_workflow_input(alert=create_alert(), conversation_id="local-conversation", execution_store=queue)
    return SimpleNamespace(case=case, queue=queue, approvals=approvals, storage=storage,
                           factory=factory, admitted=admitted, path=tmp_path / "state.db")


async def pending(state, *, decision="reject"):
    workflow = state.factory()
    events = [event async for event in workflow.run(state.admitted, checkpoint_storage=state.storage, stream=True)]
    request, = [e for e in events if e.type == "request_info"]
    checkpoint, = [c for c in await state.storage.list_checkpoints(workflow_name=workflow.name)
                   if c.pending_request_info_events]
    state.approvals.register(build_pending_approval_correlation(request=request.data,
        request_id=request.request_id, checkpoint_id=checkpoint.checkpoint_id))
    state.queue.enqueue(decision_context(request.data, decision=decision))
    return request, checkpoint


def worker(state, *, factory=None, queue=None):
    notifications = []
    async def processor(**kwargs):
        return await process_authorized_incident_approval(**kwargs, checkpoint_storage=state.storage)
    async def notify(**kwargs): notifications.append(kwargs["processed"])
    result = IncidentContinuationWorker(IncidentContinuationWorkerDependencies(
        continuation_store=queue or state.queue, approval_store=state.approvals,
        workflow_factory=factory or state.factory, processor=processor, terminal_notifier=notify))
    return result, notifications


@pytest.mark.asyncio
async def test_same_durable_identity_reaches_checkpoint_approval_queue_and_completed_rejection(tmp_path):
    state = setup(tmp_path)
    request, checkpoint = await pending(state)
    execution_id = state.admitted.execution_id
    assert request.data.workflow_id == execution_id
    assert checkpoint.state[EXECUTION_ID_STATE_KEY] == execution_id
    codec = WorkflowCheckpointCodec(allowed_types=frozenset(admitted_incident_checkpoint_allowed_types()))
    assert codec.decode(codec.encode(checkpoint)).state[EXECUTION_ID_STATE_KEY] == execution_id
    assert state.queue.get(request.data.approval_id).execution_id == execution_id
    before_calls = list(state.case.agents.calls)
    consumer, notifications = worker(state)
    assert (await consumer.process_next_once()).value == "completed"
    assert len(notifications) == 1
    assert state.approvals.get_consumption_record(request.data.approval_id) == ("completed", False)
    assert state.queue.get(request.data.approval_id).attempt_count == 1
    assert (await consumer.process_next_once()).value == "idle"
    assert state.case.agents.calls == before_calls and "azure_operations" not in before_calls


@pytest.mark.asyncio
async def test_candidate_entry_reopens_from_disk_and_requires_explicit_candidate_codec(tmp_path):
    state = setup(tmp_path)
    await pending(state)
    reopened = FileCheckpointStorage(tmp_path / "checkpoints",
        allowed_checkpoint_types=admitted_incident_checkpoint_allowed_types())
    checkpoints = await reopened.list_checkpoints(workflow_name="incident-resolution")
    candidate_codec = WorkflowCheckpointCodec(allowed_types=frozenset(admitted_incident_checkpoint_allowed_types()))
    legacy_codec = WorkflowCheckpointCodec(allowed_types=frozenset(incident_checkpoint_allowed_types()))
    entry_payloads = []
    for checkpoint in checkpoints:
        payload = candidate_codec.encode(checkpoint)
        assert candidate_codec.decode(payload).checkpoint_id == checkpoint.checkpoint_id
        try:
            legacy_codec.decode(payload)
        except WorkflowCheckpointException as exc:
            assert "AdmittedIncidentWorkflowInput" in str(exc)
            entry_payloads.append(payload)
    assert entry_payloads


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["release", "installation", "foundry", "procedures"])
async def test_incompatible_native_consumer_does_not_spend_retry_budget(tmp_path, change):
    state = setup(tmp_path / "original")
    await pending(state)
    other = candidate(tmp_path / "other", approved=change == "procedures")
    if change == "release": other.affinity = replace(other.affinity, release=replace(other.affinity.release, release_id="other"))
    if change == "installation": other.affinity = replace(other.affinity, installation_id="other")
    if change == "foundry":
        other.agents.deployment_fingerprint = "f"*64
        other.affinity = replace(other.affinity, foundry_sha256="f"*64)
    queue = SqliteExecutionStore(state.path, execution_affinity=other.affinity, payload_codec=CODEC, approval_store=state.approvals)
    factory = configured(other, queue, state.approvals, state.storage)
    consumer, notifications = worker(state, queue=queue, factory=factory)
    before = snapshot(state.path)
    for _ in range(4): assert (await consumer.process_next_once()).value == "idle"
    assert snapshot(state.path) == before and notifications == [] and other.agents.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["missing", "unknown", "conversation", "alert", "raw"])
async def test_unadmitted_or_modified_input_never_reaches_first_agent(tmp_path, change):
    state = setup(tmp_path)
    value = state.admitted
    if change == "missing": value = IncidentWorkflowInput(alert=value.alert, conversation_id=value.conversation_id)
    elif change == "unknown": value = replace(value, execution_id="wf-unknown")
    elif change == "conversation": value = replace(value, conversation_id="other")
    elif change == "alert": value = replace(value, alert=value.alert.model_copy(update={"description": "changed"}))
    elif change == "raw": value = value.alert
    before = snapshot(state.path)
    with pytest.raises(Exception):
        async for _ in state.factory().run(value, checkpoint_storage=state.storage, stream=True): pass
    assert state.case.agents.calls == [] and snapshot(state.path) == before


@pytest.mark.asyncio
async def test_assignment_is_committed_before_entry_checkpoint_and_first_agent(tmp_path):
    state = setup(tmp_path)
    observed = []
    async def first(prompt):
        record = state.queue.get_execution(state.admitted.execution_id)
        assert record.affinity == state.case.affinity
        assert await state.storage.list_checkpoints(workflow_name="incident-resolution")
        observed.append(record.execution_id)
        raise RuntimeError("stop-before-provider")
    state.case.agents.run_classification = first
    with pytest.raises(Exception):
        async for _ in state.factory().run(state.admitted, checkpoint_storage=state.storage, stream=True): pass
    assert observed == [state.admitted.execution_id]


@pytest.mark.asyncio
async def test_changed_factory_configuration_fails_before_claim(tmp_path):
    state = setup(tmp_path)
    await pending(state)
    consumer, _ = worker(state)
    state.case.agents.deployment_fingerprint = "f"*64
    before = snapshot(state.path)
    with pytest.raises(ValueError, match="Foundry"):
        await consumer.process_next_once()
    assert snapshot(state.path) == before


def test_worker_rejects_factory_bound_to_another_queue(tmp_path):
    state = setup(tmp_path)
    other = SqliteExecutionStore(state.path, execution_affinity=state.case.affinity,
                                 payload_codec=CODEC, approval_store=state.approvals)
    with pytest.raises(ValueError, match="exact execution store"):
        worker(state, queue=other)


@pytest.mark.asyncio
async def test_r1_graph_cannot_adopt_admitted_checkpoint(tmp_path):
    state = setup(tmp_path)
    _, checkpoint = await pending(state)
    with pytest.raises(WorkflowCheckpointException):
        async for _ in graph(state.case).run(checkpoint_id=checkpoint.checkpoint_id,
                                             checkpoint_storage=state.storage, stream=True): pass
