"""Real SDK checkpoints bind configuration; these tests invoke only fake agents."""
import pytest
from agent_framework import InMemoryCheckpointStorage
from agent_framework.exceptions import WorkflowCheckpointException

from src.workflows.incident_resolution.workflow import build_incident_resolution_workflow
from tests.config.test_foundry_deployment import deployment_document, environment, build_foundry_deployment_configuration
from tests.workflows.incident_resolution.test_incident_workflow import create_alert
from tests.workflows.incident_resolution.test_incident_workflow_azure_operations import AzureWorkflowFakeFoundryAgents


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["same", "customer", "read_version", "cognitive_version", "write_version",
                                  "connection", "identity", "read_host", "legacy", "legacy_to_configured"])
async def test_native_restore_requires_same_foundry_configuration(change):
    initial = environment(deployment_document())
    initial_config = build_foundry_deployment_configuration(initial)
    agents = AzureWorkflowFakeFoundryAgents()
    if change != "legacy_to_configured":
        agents.deployment_fingerprint = initial_config.fingerprint
    workflow = build_incident_resolution_workflow(agents=agents)
    storage = InMemoryCheckpointStorage()
    request_ids = []
    async for event in workflow.run(create_alert(), stream=True, checkpoint_storage=storage):
        if event.type == "request_info":
            request_ids.append(event.request_id)
    assert len(request_ids) == 1 and "azure_operations" not in agents.calls
    checkpoints = await storage.list_checkpoints(workflow_name=workflow.name)
    pending = [c for c in checkpoints if c.pending_request_info_events]
    assert len(pending) == 1
    changed = deployment_document("b" if change == "customer" else "a")
    if change == "read_version":
        changed["read"]["agent_version"] = "2"
    if change == "cognitive_version":
        changed["agents"]["knowledge"]["version"] = "9"
    if change == "write_version":
        changed["agents"]["azure_operations"]["version"] = "9"
        changed["write"]["agent_version"] = "9"
    if change == "connection":
        changed["read"]["connection_reference"] = "replacement-connection"
    if change == "read_host":
        changed["read"]["server_url"] = "https://replacement-read.invalid/"
    values = environment(changed)
    if change == "identity":
        values["FOUNDRY_MANAGED_IDENTITY_CLIENT_ID"] = "11111111-1111-4111-8111-111111111111"
    resumed_agents = AzureWorkflowFakeFoundryAgents()
    if change != "legacy":
        resumed_agents.deployment_fingerprint = build_foundry_deployment_configuration(values).fingerprint
    resumed = build_incident_resolution_workflow(agents=resumed_agents)
    async def restore():
        return [event async for event in resumed.run(
            checkpoint_id=pending[0].checkpoint_id, checkpoint_storage=storage, stream=True)]
    if change == "same":
        events = await restore()
        assert [e.request_id for e in events if e.type == "request_info"] == request_ids
        assert not [e for e in events if e.type == "output"]
    else:
        with pytest.raises(WorkflowCheckpointException):
            await restore()
    assert resumed_agents.calls == []
