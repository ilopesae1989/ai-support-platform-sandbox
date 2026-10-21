"""F27-B02-2.6: configured READ selection and causal dispatch boundaries.

The configuration, binding registry, executor and dispatch ledger are real.
Foundry responses are existing offline fixtures; no provider is constructed.
These tests establish local selection and rejection, not remote execution,
effective identity/RBAC, or the deployed consumer's G6 evidence.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import re

import pytest
from agent_framework import WorkflowBuilder

from src.agents.catalog import AgentKey
from src.config.foundry_capability_bindings import (
    build_capability_foundry_agent_binding_registry,
)
from src.workflows.incident_resolution.azure_read_tool_authority import (
    AzureReadToolAuthorityRegistry,
)
from src.workflows.incident_resolution.capability_foundry_agent_binding import (
    CapabilityFoundryAgentBindingError,
    CapabilityFoundryAgentBindingRegistry,
    CapabilityFoundryAgentBindingRegistryError,
)
from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
)
from src.workflows.incident_resolution.operation_dispatch_ledger import (
    InMemoryOperationDispatchLedger,
)
from tests.workflows.incident_resolution.test_azure_read_tool_authority import (
    FakeGovernedReadAgents,
    first_approval_response,
    verified_read_request,
)


CAPABILITY_ID = "azure.resource_group.list"
SELECTED_NAME = "agent-azure-operations-rg-list-sbx"
PROJECT_ENDPOINT = (
    "https://aif-icenter-sbx-eus2.services.ai.azure.com"
    "/api/projects/aifproj-icenter-sbx"
)


def _configured_registry():
    return build_capability_foundry_agent_binding_registry(
        environment={
            "FOUNDRY_CAPABILITY_BINDING_PROFILE": "azure-resource-group-list-sbx-v1",
            "FOUNDRY_PROJECT_ENDPOINT": PROJECT_ENDPOINT,
        }
    )


class RecordingReadAgents(FakeGovernedReadAgents):
    """Require an explicit descriptor; preserve historical fixture interfaces."""

    async def begin_azure_operations(self, message, *, agent_definition):
        self.begin_calls.append((message, agent_definition))
        return self.invocation


class RecordingDispatchLedger(InMemoryOperationDispatchLedger):
    """Observe claim attempts while retaining the real monotonic implementation."""

    def __init__(self):
        super().__init__()
        self.claim_calls = []

    def claim(self, operation_id):
        self.claim_calls.append(operation_id)
        return super().claim(operation_id)


def _workflow(*, registry, response=None, read_authorities=None):
    if response is None:
        response = first_approval_response()
    agents = RecordingReadAgents(response)
    ledger = RecordingDispatchLedger()
    executor = AzureOperationsExecutor(
        agents=agents,
        operation_dispatch_ledger=ledger,
        capability_foundry_agent_binding_registry=registry,
        azure_read_tool_authority_registry=read_authorities,
    )
    workflow = WorkflowBuilder(
        start_executor=executor,
        output_from=[executor],
        name="f27-b02-2-6-configured-read-boundary",
    ).build()
    return workflow, agents, ledger


async def _run(workflow, request):
    outputs = []
    async for event in workflow.run(request, stream=True):
        if event.type == "output":
            outputs.append(event.data)
    return outputs


def _assert_no_claim_or_provider_calls(agents, ledger):
    assert ledger.claim_calls == []
    assert ledger.count() == 0
    assert agents.begin_calls == []
    assert agents.continue_calls == []
    assert agents.legacy_calls == []


def _assert_rejected_before_continue(
    *, outputs, agents, ledger, request, binding, expected_error
):
    assert ledger.claim_calls == [request.operation_id]
    assert ledger.count() == 1
    assert len(agents.begin_calls) == 1
    assert agents.begin_calls[0][1] is binding.agent_definition
    assert agents.continue_calls == []
    assert agents.legacy_calls == []
    assert len(outputs) == 1
    assert outputs[0].operation_id == request.operation_id
    assert outputs[0].success is False
    assert outputs[0].technical_success is False
    assert outputs[0].evidence is None
    assert outputs[0].error == expected_error


@pytest.mark.asyncio
async def test_configured_rg_list_v1_is_consumed_by_executor():
    registry = _configured_registry()
    binding = registry.get(CAPABILITY_ID)
    assert registry.count() == 1
    assert binding.agent_definition.key == AgentKey.AZURE_OPERATIONS
    assert binding.agent_definition.name == SELECTED_NAME
    assert binding.agent_definition.version == "1"
    assert binding.require_approval == "always"
    assert binding.read_tool_authority.server_label == "azure-mcp-operations-sbx"
    assert binding.read_tool_authority.tool_name == "group_list"
    assert binding.read_tool_authority.argument_bindings == (
        ("subscription", "subscription_id"),
    )

    request = verified_read_request()
    response = first_approval_response()
    workflow, agents, ledger = _workflow(registry=registry, response=response)
    outputs = await _run(workflow, request)

    assert ledger.claim_calls == [request.operation_id]
    assert ledger.count() == 1
    assert len(agents.begin_calls) == 1
    assert agents.begin_calls[0][1] is binding.agent_definition
    assert len(agents.continue_calls) == 1
    continued = agents.continue_calls[0]
    assert continued["invocation"] is agents.invocation
    assert continued["approval_request"] is response.user_input_requests[0]
    assert continued["approved"] is True
    assert agents.legacy_calls == []
    assert len(outputs) == 1
    assert outputs[0].error is None
    # The fake final response is a local control, not evidence of MCP execution.


@pytest.mark.asyncio
@pytest.mark.parametrize("registry_case", ("empty", "other-capability-only"))
async def test_missing_configured_binding_rejects_before_claim(registry_case):
    if registry_case == "empty":
        registry = build_capability_foundry_agent_binding_registry(environment={})
        assert registry.count() == 0
    else:
        binding = _configured_registry().get(CAPABILITY_ID)
        other_id = "azure.test_only.other.list"
        # Test-local registry only; the product capability registry is unchanged.
        other_binding = replace(
            binding,
            capability=replace(binding.capability, capability_id=other_id),
            read_tool_authority=replace(
                binding.read_tool_authority, capability_id=other_id
            ),
        )
        registry = CapabilityFoundryAgentBindingRegistry(bindings=(other_binding,))
        assert registry.count() == 1
        assert registry.get(other_id) is other_binding

    workflow, agents, ledger = _workflow(registry=registry)
    with pytest.raises(
        CapabilityFoundryAgentBindingRegistryError,
        match="^" + re.escape(
            "No existe binding de agente Foundry para esta capability."
        ) + "$",
    ):
        await _run(workflow, verified_read_request())
    _assert_no_claim_or_provider_calls(agents, ledger)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    (("tool_name", "subscription_list"), ("server_label", "other-mcp-server")),
    ids=("wrong-tool", "wrong-server"),
)
async def test_configured_binding_rejects_substituted_authority_before_claim(
    field, value
):
    registry = _configured_registry()
    binding = registry.get(CAPABILITY_ID)
    alternate = AzureReadToolAuthorityRegistry(
        authorities=(replace(binding.read_tool_authority, **{field: value}),)
    )
    workflow, agents, ledger = _workflow(
        registry=registry, read_authorities=alternate
    )
    with pytest.raises(
        CapabilityFoundryAgentBindingError,
        match="^" + re.escape(
            "Resolucion de capability o tool MCP distinta del binding."
        ) + "$",
    ):
        await _run(workflow, verified_read_request())
    _assert_no_claim_or_provider_calls(agents, ledger)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("multiple_source", "expected_error"),
    (
        (
            "raw",
            "ValueError: La operación Azure WRITE requiere exactamente un "
            "mcp_approval_request. Encontrados=2.",
        ),
        (
            "native",
            "ValueError: Azure WRITE requiere exactamente un "
            "user_input_request MCP nativo. Encontrados=2.",
        ),
    ),
    ids=("multiple-raw", "multiple-native"),
)
async def test_configured_binding_rejects_multiple_requests_before_continue(
    multiple_source, expected_error
):
    registry = _configured_registry()
    binding = registry.get(CAPABILITY_ID)
    response = first_approval_response()
    if multiple_source == "raw":
        second = deepcopy(response.raw_response.output[0])
        second.id += "-second"
        response.raw_response.output.append(second)
        assert len(response.raw_response.output) == 2
        assert len(response.user_input_requests) == 1
    else:
        second = deepcopy(response.user_input_requests[0])
        second.id += "-second"
        second.function_call.call_id = second.id
        response.user_input_requests.append(second)
        assert len(response.raw_response.output) == 1
        assert len(response.user_input_requests) == 2

    request = verified_read_request()
    workflow, agents, ledger = _workflow(registry=registry, response=response)
    outputs = await _run(workflow, request)
    _assert_rejected_before_continue(
        outputs=outputs,
        agents=agents,
        ledger=ledger,
        request=request,
        binding=binding,
        expected_error=expected_error,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("identity_field", "expected_error"),
    (
        ("native-id", "ValueError: Mismatch entre RAW y Agent Framework: native id."),
        (
            "function-call-id",
            "ValueError: Mismatch entre RAW y Agent Framework: function_call call_id.",
        ),
    ),
    ids=("native-id", "function-call-id"),
)
async def test_configured_binding_rejects_native_identity_mismatch_before_continue(
    identity_field, expected_error
):
    registry = _configured_registry()
    binding = registry.get(CAPABILITY_ID)
    response = first_approval_response()
    native = response.user_input_requests[0]
    if identity_field == "native-id":
        native.id += "-different"
    else:
        native.function_call.call_id += "-different"

    request = verified_read_request()
    workflow, agents, ledger = _workflow(registry=registry, response=response)
    outputs = await _run(workflow, request)
    _assert_rejected_before_continue(
        outputs=outputs,
        agents=agents,
        ledger=ledger,
        request=request,
        binding=binding,
        expected_error=expected_error,
    )
