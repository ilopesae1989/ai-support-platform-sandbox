"""Native MAF checkpoints with synthetic agents; no provider or operational call."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from agent_framework import InMemoryCheckpointStorage
from agent_framework.exceptions import WorkflowCheckpointException

from src.config.procedure_configuration import build_procedure_configuration
from src.config.foundry_deployment import build_foundry_deployment_configuration
from src.runtime.execution_affinity import AFFINITY_STATE_KEY, ExecutionAffinity, ProductReleaseIdentity
from src.runtime.incident_approval_processor import process_authorized_incident_approval
from src.runtime.procedure.approval_correlation import build_pending_approval_correlation
from src.runtime.procedure.approval_store import SqlitePendingApprovalStore, ApprovalAlreadyConsumedError
from src.persistence.checkpoint_codec import WorkflowCheckpointCodec
from src.workflows.incident_resolution.checkpoint_storage import incident_checkpoint_allowed_types
from src.workflows.incident_resolution.composition import IncidentWorkflowOptions, build_incident_workflow_factory
from src.workflows.incident_resolution.workflow import build_incident_resolution_workflow
from src.workflows.incident_resolution.workflow_input import IncidentWorkflowInput
from src.workflows.incident_resolution.operation_dispatch_ledger import InMemoryOperationDispatchLedger
from src.workflows.incident_resolution.wait_recheck_consumption_ledger import InMemoryWaitRecheckConsumptionLedger
from tests.config.test_f27_integrated_publication import bundle
from tests.config.test_foundry_deployment import deployment_document, environment
from tests.runtime._neutral_incident_case import decision_context
from tests.workflows.incident_resolution.test_incident_workflow_azure_operations import AzureWorkflowFakeFoundryAgents, create_alert


def candidate(tmp_path, *, approved=False):
    tmp_path.mkdir(exist_ok=True)
    procedures = build_procedure_configuration(bundle(tmp_path, approved=approved))
    deployment = build_foundry_deployment_configuration(environment(deployment_document()))
    agents = AzureWorkflowFakeFoundryAgents()
    agents.deployment_fingerprint = deployment.fingerprint
    affinity = ExecutionAffinity(installation_id="customer-a", release=ProductReleaseIdentity(
        release_id="synthetic-release-17", source_sha256="a" * 64, environment_sha256="b" * 64),
        foundry_sha256=deployment.fingerprint, procedures_sha256=procedures.fingerprint)
    return SimpleNamespace(procedures=procedures, agents=agents, affinity=affinity)


def graph(case, *, bound=True):
    return build_incident_resolution_workflow(agents=case.agents, **(
        {"execution_affinity": case.affinity, "affinity_procedures": case.procedures} if bound else {}))


async def pending(case, *, bound=True):
    storage = InMemoryCheckpointStorage()
    workflow = graph(case, bound=bound)
    alert = create_alert().model_copy(update={"raw_attributes": {AFFINITY_STATE_KEY: {"installation_id": "forged"}}})
    events = [e async for e in workflow.run(IncidentWorkflowInput(alert=alert, conversation_id="local-conversation"),
                                           checkpoint_storage=storage, stream=True)]
    request, = [e for e in events if e.type == "request_info"]
    checkpoint, = [c for c in await storage.list_checkpoints(workflow_name=workflow.name)
                   if c.pending_request_info_events]
    return storage, workflow, request, checkpoint


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["same", "installation", "release-id", "source", "runtime",
                                     "foundry", "procedures", "legacy-to-bound", "bound-to-legacy"])
async def test_native_restore_requires_exact_execution_affinity_before_handlers(tmp_path, change):
    original = candidate(tmp_path / "original")
    storage, _, request, checkpoint = await pending(original, bound=change != "legacy-to-bound")
    resumed = candidate(tmp_path / "resumed", approved=change == "procedures")
    if change == "installation": resumed.affinity = replace(resumed.affinity, installation_id="customer-b")
    elif change in {"release-id", "source", "runtime"}:
        field, value = {"release-id": ("release_id", "synthetic-release-18"),
                        "source": ("source_sha256", "e" * 64),
                        "runtime": ("environment_sha256", "e" * 64)}[change]
        resumed.affinity = replace(resumed.affinity, release=replace(resumed.affinity.release, **{field: value}))
    elif change == "foundry":
        resumed.agents.deployment_fingerprint = "e" * 64
        resumed.affinity = replace(resumed.affinity, foundry_sha256="e" * 64)
    restored = graph(resumed, bound=change != "bound-to-legacy")
    async def restore():
        return [e async for e in restored.run(checkpoint_id=checkpoint.checkpoint_id,
                                              checkpoint_storage=storage, stream=True)]
    if change == "same":
        events = await restore()
        assert [e.request_id for e in events if e.type == "request_info"] == [request.request_id]
        assert not [e for e in events if e.type == "output"]
    else:
        with pytest.raises(WorkflowCheckpointException):
            await restore()
    assert resumed.agents.calls == []


@pytest.mark.asyncio
async def test_affinity_persisted_from_trusted_factory_survives_existing_codec(tmp_path):
    case = candidate(tmp_path)
    _, _, _, checkpoint = await pending(case)
    codec = WorkflowCheckpointCodec(allowed_types=frozenset(incident_checkpoint_allowed_types()))
    decoded = codec.decode(codec.encode(checkpoint))
    assert decoded.version == "1.0"
    assert decoded.state[AFFINITY_STATE_KEY] == case.affinity.to_document()
    assert ExecutionAffinity.from_document(decoded.state[AFFINITY_STATE_KEY]) == case.affinity
    assert "forged" not in str(decoded.state[AFFINITY_STATE_KEY])


@pytest.mark.asyncio
async def test_native_entry_checkpoint_is_bound_before_first_agent_call(tmp_path):
    case = candidate(tmp_path)
    storage = InMemoryCheckpointStorage()
    observed = []
    async def refuse(prompt):
        checkpoints = await storage.list_checkpoints(workflow_name="incident-resolution")
        assert checkpoints and all(c.graph_signature_hash == workflow.graph_signature_hash for c in checkpoints)
        observed.append("entry-persisted")
        raise RuntimeError("synthetic-stop-before-agent")
    case.agents.run_classification = refuse
    workflow = graph(case)
    assert workflow.start_executor_id == "classification-affinity-" + case.affinity.fingerprint
    with pytest.raises(Exception):
        async for _ in workflow.run(create_alert(), checkpoint_storage=storage, stream=True):
            pass
    assert observed == ["entry-persisted"]
    assert "azure_operations" not in case.agents.calls


@pytest.mark.asyncio
async def test_compatible_resume_preserves_monotonic_hitl_consumption(tmp_path):
    case = candidate(tmp_path)
    storage, _, request, checkpoint = await pending(case)
    approvals = SqlitePendingApprovalStore(tmp_path / "approval.db")
    approvals.register(build_pending_approval_correlation(request=request.data,
        request_id=request.request_id, checkpoint_id=checkpoint.checkpoint_id))
    context = decision_context(request.data, decision="reject")
    result = await process_authorized_incident_approval(invocation=context, store=approvals,
        workflow=graph(case), checkpoint_storage=storage)
    assert result.approval_evidence.decision.value == "reject"
    assert approvals.get_consumption_record(request.data.approval_id) == ("completed", False)
    before = list(case.agents.calls)
    with pytest.raises(ApprovalAlreadyConsumedError):
        await process_authorized_incident_approval(invocation=context, store=approvals,
            workflow=graph(case), checkpoint_storage=storage)
    assert case.agents.calls == before and "azure_operations" not in case.agents.calls


def test_composed_factory_rebuilds_verified_procedures_and_checks_agents_each_time(tmp_path):
    case = candidate(tmp_path)
    factory = build_incident_workflow_factory(approval_store=object(), checkpoint_storage=object(),
        operation_dispatch_ledger=InMemoryOperationDispatchLedger(),
        wait_recheck_consumption_ledger=InMemoryWaitRecheckConsumptionLedger(),
        options=IncidentWorkflowOptions(agents=case.agents, procedure_configuration=case.procedures,
                                       execution_affinity=case.affinity))
    first = factory()
    case.procedures.capabilities._bindings.clear()
    second = factory()
    assert second.graph_signature_hash == first.graph_signature_hash
    case.agents.deployment_fingerprint = "e" * 64
    with pytest.raises(ValueError, match="Foundry"):
        factory()


@pytest.mark.parametrize("override", ["procedure_capability_registry", "governed_procedure_admission_policy",
                                       "resource_identity_registry", "domain_execution_registrations"])
def test_unversioned_overrides_cannot_be_combined_with_affinity(tmp_path, override):
    case = candidate(tmp_path)
    with pytest.raises(ValueError, match="overrides"):
        build_incident_resolution_workflow(agents=case.agents, execution_affinity=case.affinity,
            affinity_procedures=case.procedures, **{override: object()})
    assert case.agents.calls == []


@pytest.mark.parametrize("change", ["missing-procedures", "changed-procedures", "missing-agents", "wrong-affinity-type"])
def test_incomplete_candidate_composition_fails_before_creating_graph(tmp_path, change):
    case = candidate(tmp_path / "one")
    args = dict(agents=case.agents, procedure_configuration=case.procedures, execution_affinity=case.affinity)
    if change == "missing-procedures": args["procedure_configuration"] = None
    elif change == "changed-procedures": args["procedure_configuration"] = candidate(tmp_path / "two", approved=True).procedures
    elif change == "missing-agents": args["agents"] = None
    else: args["execution_affinity"] = object()
    with pytest.raises((ValueError, TypeError)):
        IncidentWorkflowOptions(**args)
