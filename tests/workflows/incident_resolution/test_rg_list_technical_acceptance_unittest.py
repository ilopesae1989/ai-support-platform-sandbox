"""H12 regression against the real transition gate; no SDK, network or stubs."""
import unittest

from src.runtime.procedure.models import ProcedureRuntimeState, StepEvidence
from src.workflows.incident_resolution.operation_models import OperationResult
from src.workflows.incident_resolution.operation_evidence import OperationEvidence
from src.workflows.incident_resolution.procedure_validation_models import ProcedureValidationContext
from src.workflows.incident_resolution.procedure_transition_gate import apply_procedure_validation_transition_with_outcome


def scenario(kind="ok", proposed="resolved", legacy=False, last=True):
    identity = dict(operation_id="test-op", workflow_id="test-wf", approval_id="test-approval",
                    alert_id="test-alert", correlation_id="test-correlation", conversation_id="test-conversation",
                    procedure_id="test-procedure", procedure_version="1", current_step=1, step_id="read",
                    operation_domain="azure", operation_kind="read", operation_action="resource_group_list",
                    capability_id="azure.resource_group.list", hitl_required=True, next_action="execute_step",
                    target_resource="subscription", required_parameters=["subscription_id"],
                    resolved_parameters=[dict(name="subscription_id", value="11111111-1111-4111-8111-111111111111", source="trusted")])
    if legacy:
        identity.update(operation_action=None, capability_id=None, hitl_required=None)
    proof = None
    if kind not in ("missing", "timeout"):
        status = 500 if kind == "failure" else 200
        output = {"status": status, "results": {"groups": []}}
        if kind == "unknown":
            output = {"message": "completed"}
        proof = OperationEvidence(**identity,
            mcp_calls=[dict(mcp_call_id="call-1", tool_name="group_list", server_name="azure-mcp-operations-sbx",
                           arguments={"subscription": identity["resolved_parameters"][0]["value"]})],
            mcp_results=[dict(mcp_call_id="other-call" if kind == "wrong-call" else "call-1", output=output)],
            response_errors=[dict(message="explicit error")] if kind == "contradiction" else [])
    technical = proof.derive_technical_success() if proof is not None else None
    operation = OperationResult(**identity, success=kind != "timeout", technical_success=technical,
                                evidence=proof, error="timeout" if kind == "timeout" else None)
    step = dict(id="read", description="Read approved subscription", step_type="validation",
                operation_domain="azure", operation_kind="read", operation_action=identity["operation_action"],
                capability_id=identity["capability_id"], hitl_required=identity["hitl_required"],
                target_resource="subscription", required_parameters=["subscription_id"],
                expected_result="Technical success with evidence", verification="Trusted operation evidence")
    state = ProcedureRuntimeState(workflow_id=identity["workflow_id"], approval_id=identity["approval_id"],
        alert_id=identity["alert_id"], correlation_id=identity["correlation_id"], conversation_id=identity["conversation_id"],
        procedure=dict(id=identity["procedure_id"], name="Test", version="1"), total_steps=1 if last else 2,
        current_step=1, step=step, resolved_parameters=identity["resolved_parameters"],
        workflow_status="waiting_validation", step_status="waiting_validation", approval_status="approved",
        operation_result=StepEvidence(success=operation.success, error=operation.error, result=operation.model_dump(mode="json")))
    context = ProcedureValidationContext.model_validate(dict(request=dict(operation_result=operation,
        step=dict(procedure_id=identity["procedure_id"], procedure_version="1", current_step=1, step_id="read",
                  description=step["description"], expected_result=step["expected_result"], verification=step["verification"])),
        result=dict(operation_id=identity["operation_id"], validation_status="satisfied", proposed_next_action=proposed,
                    validation_summary="Cognitive proposal", escalation=dict(required=False))))
    return state, context


class RgListTechnicalAcceptance(unittest.TestCase):
    def assert_blocked(self, kind, proposed="resolved"):
        state, context = scenario(kind, proposed)
        original = state.model_dump(mode="json")
        outcome = apply_procedure_validation_transition_with_outcome(state=state, context=context)
        self.assertEqual(outcome.decision.next_action, "blocked")
        self.assertEqual(outcome.state.workflow_status, "blocked")
        self.assertEqual(outcome.state.step_status, "blocked")
        self.assertFalse(outcome.state.verification_result.success)
        self.assertEqual(outcome.state.current_step, 1)
        self.assertEqual(outcome.state.retry_count, 0)
        self.assertEqual(state.model_dump(mode="json"), original)
        self.assertEqual(outcome.state.operation_result, state.operation_result)
        self.assertEqual(outcome.state.verification_result.result["cognitive_proposal"]["validation_status"], "satisfied")

    def test_explicit_failure_blocks_satisfied(self): self.assert_blocked("failure")
    def test_missing_evidence_blocks_satisfied(self): self.assert_blocked("missing")
    def test_unknown_evidence_blocks_satisfied(self): self.assert_blocked("unknown")
    def test_wrong_call_evidence_blocks_satisfied(self): self.assert_blocked("wrong-call")
    def test_contradictory_error_blocks_satisfied(self): self.assert_blocked("contradiction")
    def test_timeout_blocks_satisfied(self): self.assert_blocked("timeout")
    def test_failure_cannot_implicitly_retry(self): self.assert_blocked("failure", "repeat")
    def test_unknown_cannot_continue(self): self.assert_blocked("unknown", "continue")
    def test_proven_success_can_resolve(self):
        state, context = scenario()
        out = apply_procedure_validation_transition_with_outcome(state=state, context=context)
        self.assertEqual(out.state.workflow_status, "resolved")
        self.assertTrue(out.state.verification_result.success)
    def test_proven_success_can_continue(self):
        state, context = scenario(proposed="continue", last=False)
        out = apply_procedure_validation_transition_with_outcome(state=state, context=context)
        self.assertEqual(out.decision.next_action, "continue")
        self.assertEqual(out.state.step_status, "succeeded")
        self.assertEqual(out.state.current_step, state.current_step)
    def test_last_step_continue_resolves_only_with_proof(self):
        state, context = scenario(proposed="continue")
        out = apply_procedure_validation_transition_with_outcome(state=state, context=context)
        self.assertEqual(out.decision.next_action, "resolved")
    def test_legacy_contract_unchanged(self):
        state, context = scenario("missing", legacy=True)
        out = apply_procedure_validation_transition_with_outcome(state=state, context=context)
        self.assertEqual(out.decision.next_action, "resolved")
    def test_wrong_runtime_capability_rejected(self):
        state, context = scenario()
        state.step.capability_id = "azure.vm.start"
        with self.assertRaises(ValueError):
            apply_procedure_validation_transition_with_outcome(state=state, context=context)
    def test_missing_runtime_action_rejected(self):
        state, context = scenario()
        state.step.operation_action = None
        with self.assertRaises(ValueError):
            apply_procedure_validation_transition_with_outcome(state=state, context=context)
    def test_different_hitl_policy_rejected(self):
        state, context = scenario()
        state.step.hitl_required = False
        with self.assertRaises(ValueError):
            apply_procedure_validation_transition_with_outcome(state=state, context=context)
    def test_different_registered_result_rejected(self):
        state, context = scenario()
        state.operation_result.result["response_text"] = "substitution"
        with self.assertRaises(ValueError):
            apply_procedure_validation_transition_with_outcome(state=state, context=context)
    def test_replay_rejected(self):
        state, context = scenario()
        out = apply_procedure_validation_transition_with_outcome(state=state, context=context)
        with self.assertRaises(ValueError):
            apply_procedure_validation_transition_with_outcome(state=out.state, context=context)


if __name__ == "__main__":
    unittest.main(verbosity=2)
