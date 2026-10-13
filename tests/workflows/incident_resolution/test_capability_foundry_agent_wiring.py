"""F27.3-R13: RED contract for explicit Azure READ Foundry agent selection.

Synthetic offline fakes only. Does not run a Foundry agent, MCP tool or Azure client.
The known R12 gaps must fail through named pytest markers, not import errors.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from agent_framework import WorkflowBuilder

from src.agents.catalog import AgentKey, FoundryAgentDefinition, build_agent_catalog
from src.runtime.procedure.models import OperationAction
from src.workflows.incident_resolution import workflow as workflow_module
from src.workflows.incident_resolution.azure_domain_composition import (
    build_azure_domain_composition,
)
from src.workflows.incident_resolution.azure_read_tool_authority import (
    AzureReadToolAuthorityRegistry,
    build_default_azure_read_tool_authority_registry,
)
from src.workflows.incident_resolution.capability_foundry_agent_binding import (
    CapabilityFoundryAgentBinding,
    CapabilityFoundryAgentBindingRegistry,
    CapabilityFoundryAgentBindingRegistryError,
)
from src.workflows.incident_resolution.capability_registry import (
    build_default_capability_registry,
)
from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
)
from src.workflows.incident_resolution.operation_dispatch_ledger import (
    InMemoryOperationDispatchLedger,
)
from tests.workflows.incident_resolution.test_azure_domain_composition import (
    assert_no_dependency_calls,
    dependencies,
)
from tests.workflows.incident_resolution.test_azure_read_tool_authority import (
    FakeGovernedReadAgents,
    first_approval_response,
    verified_read_request,
)

CAPABILITY_ID = "azure.resource_group.list"
RED_PREFIX = "F27_3_R13_EXPECTED_RED_"
SELECTED_NAME = "agent-synthetic-rg-read-safe"


def _binding_registry():
    capability = build_default_capability_registry().get(CAPABILITY_ID)
    read_authority = build_default_azure_read_tool_authority_registry().get(CAPABILITY_ID)
    definition = FoundryAgentDefinition(
        key=AgentKey.AZURE_OPERATIONS,
        name=SELECTED_NAME,
        version="2",
    )
    binding = CapabilityFoundryAgentBinding(
        capability=capability,
        read_tool_authority=read_authority,
        agent_definition=definition,
        require_approval="always",
    )
    return CapabilityFoundryAgentBindingRegistry(bindings=(binding,)), definition, read_authority


class RecordingReadAgents(FakeGovernedReadAgents):
    """No provider calls: the existing certified F27.1 RAW/native fake responses."""

    async def begin_azure_operations(self, message, *, agent_definition=None):
        self.begin_calls.append((message, agent_definition))
        return self.invocation


def _build_selector_workflow(*, registry, read_authorities=None):
    agents = RecordingReadAgents(first_approval_response())
    ledger = InMemoryOperationDispatchLedger()
    executor = AzureOperationsExecutor(
        agents=agents,
        operation_dispatch_ledger=ledger,
        capability_foundry_agent_binding_registry=registry,
        azure_read_tool_authority_registry=read_authorities,
    )
    workflow = WorkflowBuilder(
        start_executor=executor,
        output_from=[executor],
        name="f273-r13-offline-selector-test",
    ).build()
    return workflow, agents, ledger


async def _run(workflow, request):
    outputs = []
    async for event in workflow.run(request, stream=True):
        if event.type == "output":
            outputs.append(event.data)
    return outputs


def _red_when(condition, reason):
    if not condition:
        pytest.fail(RED_PREFIX + reason, pytrace=False)


@pytest.mark.asyncio
async def test_red_selected_governed_read_pins_exact_agent_not_catalog():
    registry, expected, _ = _binding_registry()
    workflow, agents, ledger = _build_selector_workflow(registry=registry)
    await _run(workflow, verified_read_request())
    _red_when(
        len(agents.begin_calls) == 1
        and agents.begin_calls[0][1] is expected
        and len(agents.continue_calls) == 1
        and agents.legacy_calls == []
        and ledger.count() == 1,
        "EXECUTOR_IGNORES_EXPLICIT_PINNED_AGENT_BINDING",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "request_changes",
    [
        {"operation_action": OperationAction.VM_START},
        {"operation_domain": "other"},
        {"target_resource": "subscription-other"},
        {"required_parameters": []},
    ],
    ids=("wrong-action", "wrong-domain", "wrong-target", "wrong-parameters"),
)
async def test_red_governed_read_request_mismatch_rejected_before_claim(request_changes):
    registry, _, _ = _binding_registry()
    workflow, agents, ledger = _build_selector_workflow(registry=registry)
    try:
        await _run(workflow, verified_read_request(**request_changes))
    except ValueError:
        pass  # A future pre-dispatch fail-closed rejection is an allowed outcome.
    _red_when(
        ledger.count() == 0
        and agents.begin_calls == []
        and agents.continue_calls == []
        and agents.legacy_calls == [],
        "REQUEST_NOT_CROSSCHECKED_WITH_CANONICAL_CAPABILITY_BEFORE_DISPATCH",
    )


@pytest.mark.asyncio
async def test_red_explicit_registry_missing_binding_fails_before_claim_no_fallback():
    registry = CapabilityFoundryAgentBindingRegistry(bindings=())
    workflow, agents, ledger = _build_selector_workflow(registry=registry)
    try:
        await _run(workflow, verified_read_request())
    except (ValueError, CapabilityFoundryAgentBindingRegistryError):
        pass
    _red_when(
        ledger.count() == 0
        and agents.begin_calls == []
        and agents.continue_calls == []
        and agents.legacy_calls == [],
        "EXPLICIT_MISSING_BINDING_FALLS_BACK_TO_DEFAULT_V13",
    )


@pytest.mark.asyncio
async def test_red_substituted_read_tool_authority_fails_before_claim():
    registry, _, read_authority = _binding_registry()
    wrong_authority = replace(read_authority, tool_name="subscription_list")
    alternate = AzureReadToolAuthorityRegistry(authorities=(wrong_authority,))
    workflow, agents, ledger = _build_selector_workflow(
        registry=registry, read_authorities=alternate,
    )
    try:
        await _run(workflow, verified_read_request())
    except ValueError:
        pass
    _red_when(
        ledger.count() == 0
        and agents.begin_calls == []
        and agents.continue_calls == []
        and agents.legacy_calls == [],
        "SELECTOR_ACCEPTS_SUBSTITUTED_READ_TOOL_AUTHORITY_BEFORE_DISPATCH",
    )


def test_red_composition_factory_propagates_exact_binding_registry():
    registry, _, _ = _binding_registry()
    deps = dependencies()  # Existing F26 fake dependencies, no network.
    try:
        composition = build_azure_domain_composition(
            **deps, capability_foundry_agent_binding_registry=registry,
        )
    except TypeError:
        pytest.fail(RED_PREFIX + "AZURE_FACTORY_NO_EXPLICIT_BINDING_INJECTION", pytrace=False)
    executor = composition.execution_binding.executor
    _red_when(
        executor._capability_foundry_agent_binding_registry is registry,
        "AZURE_FACTORY_DOES_NOT_FORWARD_BINDING_TO_OWN_EXECUTOR",
    )
    assert_no_dependency_calls(deps)


def test_red_workflow_root_forwards_binding_registry_once_without_new_nodes(monkeypatch):
    registry, _, _ = _binding_registry()
    deps = dependencies()
    seen = []
    published_factory = build_azure_domain_composition

    def factory_spy(**kwargs):
        seen.append(dict(kwargs))
        return published_factory(**kwargs)

    monkeypatch.setattr(workflow_module, "build_azure_domain_composition", factory_spy)
    try:
        workflow = workflow_module.build_incident_resolution_workflow(
            **deps, capability_foundry_agent_binding_registry=registry,
        )
    except TypeError:
        pytest.fail(RED_PREFIX + "WORKFLOW_ROOT_NO_BINDING_INJECTION", pytrace=False)
    _red_when(
        workflow is not None
        and len(seen) == 1
        and seen[0].get("capability_foundry_agent_binding_registry") is registry,
        "WORKFLOW_ROOT_DID_NOT_FORWARD_EXACT_SELECTOR_ONCE",
    )
    assert_no_dependency_calls(deps)


@pytest.mark.asyncio
async def test_guard_legacy_read_ignores_explicit_selector_and_uses_single_run():
    registry, _, _ = _binding_registry()
    workflow, agents, ledger = _build_selector_workflow(registry=registry)
    outputs = await _run(workflow, verified_read_request(capability_id=None))
    assert agents.begin_calls == []
    assert agents.continue_calls == []
    assert len(agents.legacy_calls) == 1
    assert ledger.count() == 1
    assert len(outputs) == 1


def test_guard_catalog_preserves_vm_start_v13_and_excludes_probe(monkeypatch):
    monkeypatch.delenv("FOUNDRY_AGENT_AZURE_OPERATIONS_VERSION", raising=False)
    definitions = build_agent_catalog()
    assert definitions[AgentKey.AZURE_OPERATIONS].name == "agent-azure-operations-sbx"
    assert definitions[AgentKey.AZURE_OPERATIONS].version == "13"
    assert all(
        item.name != "agent-f27-rg-list-pause-probe-sbx"
        for item in definitions.values()
    )


def test_guard_default_procedure_bindings_vm_start_only():
    manifest = (
        Path(__file__).resolve().parents[3]
        / "src/workflows/incident_resolution/procedure_capability_bindings.v1.json"
    )
    records = json.loads(manifest.read_text(encoding="utf-8"))["bindings"]
    assert len(records) == 3
    assert all(row["capability_id"] == "azure.vm.start" for row in records)


def test_guard_binding_resolution_is_exact_and_not_llm_driven():
    registry, expected, authority = _binding_registry()
    capability = build_default_capability_registry().get(CAPABILITY_ID)
    assert registry.resolve(capability=capability, read_tool_authority=authority) is expected
    with pytest.raises(CapabilityFoundryAgentBindingRegistryError):
        registry.get("Azure.Resource_Group.List")
    with pytest.raises(CapabilityFoundryAgentBindingRegistryError):
        registry.get("azure.resource_group.list ")
