"""Selected READ authority must survive the real executor -> gate boundary."""
import copy

import pytest

from src.runtime.procedure.models import StepEvidence
from src.workflows.incident_resolution.azure_read_tool_authority import AzureReadToolAuthorityRegistry
from src.workflows.incident_resolution.procedure_validation_models import ProcedureValidationContext
from src.workflows.incident_resolution.operation_models import OperationResult
from src.workflows.incident_resolution.executors.procedure_transition import ProcedureTransitionExecutor
from tests.config.test_foundry_deployment import deployment_document, environment, build_foundry_deployment_configuration
from tests.workflows.incident_resolution.test_rg_list_technical_acceptance_unittest import scenario
from tests.workflows.incident_resolution.test_procedure_transition_executor import FakeWorkflowContext, load_stored_state


def selected_scenario(label, *, output=None, change_call=None):
    state, context = scenario()
    payload = context.request.operation_result.model_dump(mode="python")
    call = payload["evidence"]["mcp_calls"][0]
    call["server_name"] = label
    if change_call:
        call.update(change_call)
    if output is not None:
        payload["evidence"]["mcp_results"][0]["output"] = copy.deepcopy(output)
    operation = OperationResult.model_validate(payload)
    state.operation_result = StepEvidence(success=operation.success, error=operation.error,
                                          result=operation.model_dump(mode="json"))
    context_payload = context.model_dump(mode="python")
    context_payload["request"]["operation_result"] = operation
    return state, ProcedureValidationContext.model_validate(context_payload)


@pytest.mark.asyncio
@pytest.mark.parametrize("customer", ["a", "b"])
async def test_selected_isolated_read_passes_real_transition_executor(customer):
    cfg = build_foundry_deployment_configuration(environment(deployment_document(customer)))
    authority = cfg.read_bindings.read_authority_registry()
    state, context = selected_scenario(authority.get("azure.resource_group.list").server_label)
    ctx = FakeWorkflowContext(state)
    await ProcedureTransitionExecutor(azure_read_tool_authority_registry=authority).handle(context, ctx)
    result = load_stored_state(ctx)
    assert result.workflow_status == "resolved"
    assert result.verification_result.success is True
    assert state.workflow_status == "waiting_validation"


@pytest.mark.asyncio
@pytest.mark.parametrize("label", ["azure-mcp-operations-sbx", "mcp-b-read", "arbitrary-server"])
async def test_result_cannot_choose_its_own_authority(label):
    cfg = build_foundry_deployment_configuration(environment(deployment_document("a")))
    state, context = selected_scenario(label)
    ctx = FakeWorkflowContext(state)
    await ProcedureTransitionExecutor(azure_read_tool_authority_registry=cfg.read_bindings.read_authority_registry()).handle(context, ctx)
    assert load_stored_state(ctx).workflow_status == "blocked"


@pytest.mark.asyncio
async def test_empty_explicit_registry_never_accepts_legacy_result():
    state, context = scenario()
    ctx = FakeWorkflowContext(state)
    await ProcedureTransitionExecutor(azure_read_tool_authority_registry=AzureReadToolAuthorityRegistry(authorities=())).handle(context, ctx)
    assert load_stored_state(ctx).workflow_status == "blocked"


@pytest.mark.asyncio
@pytest.mark.parametrize("output", [
    {"status": 200}, {"status": 200, "results": {"groups": [], "nextLink": "more"}},
    '{"status":200,"status":200,"results":{"groups":[]}}',
])
async def test_selected_profile_preserves_content_rejections(output):
    cfg = build_foundry_deployment_configuration(environment(deployment_document()))
    state, context = selected_scenario("mcp-a-read", output=output)
    ctx = FakeWorkflowContext(state)
    await ProcedureTransitionExecutor(azure_read_tool_authority_registry=cfg.read_bindings.read_authority_registry()).handle(context, ctx)
    assert load_stored_state(ctx).workflow_status == "blocked"


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [
    {"tool_name": "compute_vm_start"},
    {"arguments": {"subscription": "22222222-2222-4222-8222-222222222222"}},
    {"arguments": {"subscription": "11111111-1111-4111-8111-111111111111", "extra": True}},
])
async def test_selected_profile_preserves_tool_and_parameter_rejections(change):
    cfg = build_foundry_deployment_configuration(environment(deployment_document()))
    state, context = selected_scenario("mcp-a-read", change_call=change)
    ctx = FakeWorkflowContext(state)
    await ProcedureTransitionExecutor(azure_read_tool_authority_registry=cfg.read_bindings.read_authority_registry()).handle(context, ctx)
    assert load_stored_state(ctx).workflow_status == "blocked"
