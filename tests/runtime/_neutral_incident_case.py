"""Native MAF workflow with synthetic agents; no channel or remote service."""
from types import SimpleNamespace

from agent_framework import InMemoryCheckpointStorage

from src.runtime.procedure.approval_channel import ApprovalChannelAction
from src.runtime.procedure.approval_context import ApprovalIdentity, AuthorizedApprovalContext
from src.runtime.procedure.approval_correlation import build_pending_approval_correlation
from src.runtime.procedure.approval_store import SqlitePendingApprovalStore
from src.workflows.incident_resolution.composition import IncidentWorkflowOptions, build_incident_workflow_factory
from src.workflows.incident_resolution.operation_dispatch_ledger import InMemoryOperationDispatchLedger
from src.workflows.incident_resolution.wait_recheck_consumption_ledger import InMemoryWaitRecheckConsumptionLedger
from src.workflows.incident_resolution.workflow_input import IncidentWorkflowInput
from tests.workflows.incident_resolution.test_incident_workflow_azure_operations import (
    AzureWorkflowFakeFoundryAgents, create_alert,
)


def decision_context(request, decision="approve", conversation=None):
    return AuthorizedApprovalContext(
        policy_id="local-authorized-policy",
        action=ApprovalChannelAction(approval_id=request.approval_id, decision=decision),
        identity=ApprovalIdentity(
            channel="local-test", identity_scheme="synthetic-principal",
            tenant_id="customer-a", principal_id="operator-a",
            conversation_id=conversation or request.conversation_id,
        ),
    )


async def prepare_native_case(tmp_path):
    storage = InMemoryCheckpointStorage()
    agents = AzureWorkflowFakeFoundryAgents()
    store = SqlitePendingApprovalStore(tmp_path / "approvals.db")
    factory = build_incident_workflow_factory(
        approval_store=store, checkpoint_storage=storage,
        operation_dispatch_ledger=InMemoryOperationDispatchLedger(),
        wait_recheck_consumption_ledger=InMemoryWaitRecheckConsumptionLedger(),
        options=IncidentWorkflowOptions(agents=agents),
    )
    graph = factory()
    events = [event async for event in graph.run(
        IncidentWorkflowInput(alert=create_alert(), conversation_id="local-conversation"),
        checkpoint_storage=storage, stream=True,
    )]
    requests = [event for event in events if event.type == "request_info"]
    assert len(requests) == 1
    checkpoints = await storage.list_checkpoints(workflow_name=graph.name)
    pending = [checkpoint for checkpoint in checkpoints if checkpoint.pending_request_info_events]
    assert len(pending) == 1
    store.register(build_pending_approval_correlation(
        request=requests[0].data, request_id=requests[0].request_id,
        checkpoint_id=pending[0].checkpoint_id,
    ))
    return SimpleNamespace(factory=factory, storage=storage, agents=agents, store=store,
                           request=requests[0].data, checkpoint=pending[0])
