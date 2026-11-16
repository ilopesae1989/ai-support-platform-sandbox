"""Build the real graph without a channel, retaining its existing authorities."""
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_framework import InMemoryCheckpointStorage

from src.persistence.checkpoint_codec import WorkflowCheckpointCodec
from src.workflows.incident_resolution.checkpoint_storage import incident_checkpoint_allowed_types
from src.workflows.incident_resolution.composition import (
    IncidentWorkflowOptions, build_incident_workflow_factory,
)
from src.workflows.incident_resolution.operation_dispatch_ledger import InMemoryOperationDispatchLedger
from src.workflows.incident_resolution.wait_recheck_consumption_ledger import InMemoryWaitRecheckConsumptionLedger
from tests.config.test_foundry_deployment import deployment_document, environment, build_foundry_deployment_configuration
from tests.workflows.incident_resolution.test_incident_workflow_azure_operations import AzureWorkflowFakeFoundryAgents

ROOT = Path(__file__).resolve().parents[3]


def dependencies():
    return dict(approval_store=object(), checkpoint_storage=InMemoryCheckpointStorage(),
                operation_dispatch_ledger=InMemoryOperationDispatchLedger(),
                wait_recheck_consumption_ledger=InMemoryWaitRecheckConsumptionLedger())


@pytest.mark.parametrize("customer", ["a", "b"])
def test_direct_core_build_preserves_selected_authorities_and_shared_dependencies(customer):
    config = build_foundry_deployment_configuration(environment(deployment_document(customer)))
    agents = AzureWorkflowFakeFoundryAgents()
    agents.deployment_fingerprint = config.fingerprint
    def never(*args, **kwargs):
        raise AssertionError("Composition must not read durable state or invoke a provider")
    stores = dependencies()
    stores["approval_store"] = SimpleNamespace(get_by_approval_id=never, get_by_request_id=never,
                                               get_consumption_record=never)
    stores["checkpoint_storage"] = SimpleNamespace(load=never)
    reader = SimpleNamespace(read_power_state=never)
    factory = build_incident_workflow_factory(**stores, azure_vm_power_state_reader=reader,
        options=IncidentWorkflowOptions(agents=agents,
            capability_foundry_agent_binding_registry=config.read_bindings,
            vm_start_binding=config.write_binding))
    first, second = factory(), factory()
    assert first is not second
    assert first.name == second.name == "incident-resolution"
    assert first.graph_signature_hash == second.graph_signature_hash
    assert agents.calls == []
    for graph in (first, second):
        azure = graph.executors["azure_operations"]
        transition = graph.executors["procedure_transition"]
        assert azure._agents is agents
        assert azure._operation_dispatch_ledger is stores["operation_dispatch_ledger"]
        assert transition._wait_recheck_consumption_ledger is stores["wait_recheck_consumption_ledger"]
        assert azure._capability_foundry_agent_binding_registry is config.read_bindings
        assert azure._azure_read_tool_authority_registry is transition._azure_read_tool_authority_registry
        assert azure._vm_start_route.binding is config.write_binding
        binding_reader = azure._vm_start_route.approval_binding_reader
        assert binding_reader._store is stores["approval_store"]
        assert binding_reader._checkpoint_storage is stores["checkpoint_storage"]


@pytest.mark.parametrize("missing", ["approval_store", "checkpoint_storage",
                                    "operation_dispatch_ledger", "wait_recheck_consumption_ledger"])
def test_composed_path_requires_explicit_stores(missing):
    stores = dependencies()
    stores[missing] = None
    with pytest.raises(TypeError, match=missing):
        build_incident_workflow_factory(**stores, options=IncidentWorkflowOptions())


@pytest.mark.parametrize("name", ["capability_foundry_agent_binding_registry", "vm_start_binding",
                                 "vm_start_route", "procedure_configuration", "attestation_publisher"])
def test_selection_is_validated_without_creating_dependencies(name):
    with pytest.raises(TypeError):
        IncidentWorkflowOptions(**{name: object()})


def test_explicit_falsy_agents_and_dispatch_are_not_replaced():
    class FalsyAgents(AzureWorkflowFakeFoundryAgents):
        def __bool__(self):
            return False
    class FalsyLedger(InMemoryOperationDispatchLedger):
        def __bool__(self):
            return False
    agents = FalsyAgents()
    stores = dependencies()
    stores["operation_dispatch_ledger"] = FalsyLedger()
    factory = build_incident_workflow_factory(**stores, options=IncidentWorkflowOptions(agents=agents))
    azure = factory().executors["azure_operations"]
    assert azure._agents is agents
    assert azure._operation_dispatch_ledger is stores["operation_dispatch_ledger"]


@pytest.mark.asyncio
async def test_published_pre_extraction_checkpoint_resumes_without_replaying_agents():
    payload = (ROOT / "tests/fixtures/checkpoints/incident_v1_before_e3.json").read_text(encoding="utf-8")
    codec = WorkflowCheckpointCodec(allowed_types=frozenset(incident_checkpoint_allowed_types()))
    checkpoint = codec.decode(payload)
    storage = InMemoryCheckpointStorage()
    await storage.save(checkpoint)
    agents = AzureWorkflowFakeFoundryAgents()
    stores = dependencies()
    stores["checkpoint_storage"] = storage
    graph = build_incident_workflow_factory(**stores, options=IncidentWorkflowOptions(agents=agents))()
    events = [e async for e in graph.run(checkpoint_id=checkpoint.checkpoint_id,
                                        checkpoint_storage=storage, stream=True)]
    assert [e.request_id for e in events if e.type == "request_info"] == list(checkpoint.pending_request_info_events)
    assert not [e for e in events if e.type == "output"]
    assert agents.calls == []


def test_core_build_does_not_import_channel_or_teams_sdk():
    script = '''
import importlib.abc, sys
class NoChannel(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "src.channels" or fullname.startswith(("src.channels.", "microsoft_teams")):
            raise AssertionError("Core imports channel: " + fullname)
sys.meta_path.insert(0, NoChannel())
from src.workflows.incident_resolution.composition import IncidentWorkflowOptions, build_incident_workflow_factory
from tests.workflows.incident_resolution.test_incident_workflow_azure_operations import AzureWorkflowFakeFoundryAgents
factory = build_incident_workflow_factory(approval_store=object(), checkpoint_storage=object(),
    operation_dispatch_ledger=object(), wait_recheck_consumption_ledger=object(),
    options=IncidentWorkflowOptions(agents=AzureWorkflowFakeFoundryAgents()))
assert factory().name == "incident-resolution"
'''
    result = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
