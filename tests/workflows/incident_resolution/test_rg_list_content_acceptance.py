"""Adversarial content and binding cases through the real gate and runtime."""
import copy
import json

import pytest

from src.runtime.procedure.models import StepEvidence
from src.workflows.incident_resolution.operation_models import OperationResult
from src.workflows.incident_resolution.procedure_validation_models import ProcedureValidationContext
from src.workflows.incident_resolution.procedure_transition_gate import apply_procedure_validation_transition_with_outcome
from tests.workflows.incident_resolution.test_rg_list_technical_acceptance_unittest import scenario


SUB = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
GROUP = {"name": "rg-test", "id": "/subscriptions/" + SUB + "/resourceGroups/rg-test", "location": "northeurope"}
VALID = {"status": 200, "results": {"groups": [GROUP]}}


def run_case(output, change_call=None, extra_call=False, proposed="resolved"):
    state, context = scenario(proposed=proposed)
    op = context.request.operation_result.model_dump(mode="python")
    op["evidence"]["mcp_results"][0]["output"] = copy.deepcopy(output)
    if change_call:
        op["evidence"]["mcp_calls"][0].update(change_call)
    if extra_call:
        call = copy.deepcopy(op["evidence"]["mcp_calls"][0]); call["mcp_call_id"] = "call-2"
        result = copy.deepcopy(op["evidence"]["mcp_results"][0]); result["mcp_call_id"] = "call-2"
        op["evidence"]["mcp_calls"].append(call); op["evidence"]["mcp_results"].append(result)
    from src.workflows.incident_resolution.operation_evidence import OperationEvidence
    proof = OperationEvidence.model_validate(op["evidence"])
    op["technical_success"] = proof.derive_technical_success()
    operation = OperationResult.model_validate(op)
    state.operation_result = StepEvidence(success=operation.success, error=operation.error,
                                          result=operation.model_dump(mode="json"))
    ctx = context.model_dump(mode="python"); ctx["request"]["operation_result"] = operation
    return apply_procedure_validation_transition_with_outcome(
        state=state, context=ProcedureValidationContext.model_validate(ctx))


def assert_blocked(outcome):
    assert outcome.decision.next_action == "blocked"
    assert outcome.state.workflow_status == "blocked"
    assert outcome.state.step_status == "blocked"
    assert outcome.state.current_step == 1 and outcome.state.retry_count == 0
    assert outcome.state.verification_result.success is False
    assert outcome.state.verification_result.result["cognitive_proposal"]["validation_status"] == "satisfied"


@pytest.mark.parametrize("output", [
    VALID, json.dumps(VALID), [{"type": "text", "text": json.dumps(VALID)}],
    {"status": 200, "results": {"groups": []}},
])
def test_supported_content_reaches_resolved(output):
    assert run_case(output).state.workflow_status == "resolved"


@pytest.mark.parametrize("output", [
    {"status": 200},
    {"status": 200, "results": {}},
    {"status": 200, "results": {"groups": None}},
    {"status": 200, "results": {"groups": "rg-test"}},
    {"status": 200, "results": {"groups": ["rg-test"]}},
    {"status": 200, "results": {"groups": [{"name": "rg-test"}]}},
    {"status": 200, "results": {"groups": [{**GROUP, "location": ""}]}},
    {"status": 200, "results": {"groups": [{**GROUP, "id": GROUP["id"].replace(SUB, OTHER)}]}},
    {"status": 200, "results": {"groups": [{**GROUP, "name": "another-group"}]}},
    {"status": 200, "results": {"groups": [{**GROUP, "id": GROUP["id"] + "/providers/other/x"}]}},
    {"status": 200, "results": {"groups": [GROUP, GROUP]}},
    {"status": 200, "results": {"groups": [GROUP], "nextLink": "more"}},
    {**VALID, "nextLink": "more"},
    {**VALID, "error": "contradiction"},
    {**VALID, "isError": True},
    {**VALID, "status": 201},
    {**VALID, "status": True},
    {**VALID, "status": "200"},
    {**VALID, "status": 500},
    "{\"status\":500,\"status\":200,\"results\":{\"groups\":[]}}",
    "{\"status\":200,\"results\":{\"groups\":[],\"groups\":null}}",
    "{\"status\":200,\"results\":{\"groups\":[]},\"extra\":NaN}",
    [VALID, VALID],
    [{"type": "text", "text": json.dumps(VALID)}, {"type": "image", "data": "unreviewed"}],
    {"type": "text", "text": json.dumps(VALID), "status": 200},
])
def test_success_status_does_not_substitute_for_procedure_content(output):
    assert_blocked(run_case(output))


@pytest.mark.parametrize("change", [
    {"tool_name": "compute_vm_power-state"},
    {"server_name": "another-server"},
    {"server_name": None},
    {"arguments": {}},
    {"arguments": {"subscription": OTHER}},
    {"arguments": {"subscription": SUB, "extra": True}},
])
def test_substituted_call_cannot_satisfy_rg_list(change):
    assert_blocked(run_case(VALID, change_call=change))


def test_second_call_cannot_hide_behind_two_success_statuses():
    assert_blocked(run_case(VALID, extra_call=True))


@pytest.mark.parametrize("proposed", ["resolved", "continue", "repeat"])
def test_missing_content_never_advances_or_retries(proposed):
    assert_blocked(run_case({"status": 200}, proposed=proposed))
