import importlib

import pytest

from src.runtime.procedure.models import (
    ApprovalStatus,
    NextAction,
    OperationKind,
    ProcedureExecutionResult,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    StepEvidence,
    StepStatus,
    WorkflowStatus,
)

from src.workflows.incident_resolution.continuation_context import (
    ProcedureContinuationContext,
)

from src.workflows.incident_resolution.procedure_transition_gate import (
    ProcedureTransitionOutcome,
)


BUILDER_MODULE = (
    "src.workflows.incident_resolution."
    "continuation_request_builder"
)


def load_builder():
    try:
        module = importlib.import_module(
            BUILDER_MODULE
        )
    except ModuleNotFoundError as exc:
        pytest.fail(
            "Continuation request builder "
            f"is missing: {exc}"
        )

    builder = getattr(
        module,
        "build_procedure_continuation_input",
        None,
    )

    assert callable(
        builder
    )

    return builder


def make_runtime_state():
    return ProcedureRuntimeState(
        workflow_id="wf-next-001",
        alert_id="ALT-NEXT-001",
        correlation_id="corr-next-001",
        approval_id="apr-step-001",
        conversation_id="conv-next-001",

        procedure=ProcedureReference(
            id="NTTSY-NEXT-001",
            name="Multi-step Procedure",
            version="2.0",
        ),

        total_steps=3,
        current_step=1,

        step=ProcedureStep(
            id="1",
            description="Completed step one.",
            step_type="validation",
            operation_domain="azure",
            operation_kind=OperationKind.READ,
            target_resource="vm-old-step",
            required_parameters=[],
            preconditions=[],
            expected_result="Step one succeeds.",
            verification="Verify step one.",
        ),

        resolved_parameters=[],

        workflow_status=WorkflowStatus.RUNNING,
        step_status=StepStatus.SUCCEEDED,
        approval_status=ApprovalStatus.APPROVED,

        operation_result=StepEvidence(
            success=True,
            result={
                "step": 1,
                "kind": "operation",
            },
            error=None,
        ),

        verification_result=StepEvidence(
            success=True,
            result={
                "step": 1,
                "kind": "verification",
            },
            error=None,
        ),
    )


def make_decision(
    next_action=NextAction.CONTINUE,
):
    return ProcedureExecutionResult(
        next_action=next_action,
        evidence=None,
        escalation_required=False,
        escalation_team=None,
        escalation_level=None,
        escalation_criteria=None,
    )


def make_outcome(
    *,
    state=None,
    next_action=NextAction.CONTINUE,
):
    if state is None:
        state = make_runtime_state()

    return ProcedureTransitionOutcome(
        state=state,
        decision=make_decision(
            next_action=next_action
        ),
    )


def make_continuation_context(
    *,
    procedure_found=True,
    procedure_match="exact",
    execution_eligible=True,
):
    return ProcedureContinuationContext(
        request_affected_resource="vm-authoritative-01",
        incident_description=(
            "VM alert requires the next "
            "governed procedure step."
        ),

        procedure_found=procedure_found,
        procedure_match=procedure_match,
        execution_eligible=execution_eligible,

        operational_affected_resource=(
            "vm-authoritative-01"
        ),

        resource_type=(
            "Microsoft.Compute/"
            "virtualMachines"
        ),

        service="Azure Virtual Machines",
        environment="sandbox",
        incident_origin="observed",

        subscription_id="sub-next-001",
        resource_group="rg-next-001",
        vm_name="vm-authoritative-01",
        tenant_id="tenant-next-001",
    )


def test_builder_constructs_exact_python_owned_n_plus_one_input():
    builder = load_builder()

    result = builder(
        outcome=make_outcome(),
        continuation=(
            make_continuation_context()
        ),
    )

    assert result.request.model_dump(
        mode="json"
    ) == {
        "alert_id":
            "ALT-NEXT-001",

        "procedure_found":
            True,

        "procedure_match":
            "exact",

        "execution_eligible":
            True,

        "procedure_id":
            "NTTSY-NEXT-001",

        "procedure_name":
            "Multi-step Procedure",

        "procedure_version":
            "2.0",

        "requested_step":
            2,

        "affected_resource":
            "vm-authoritative-01",

        "incident_description":
            (
                "VM alert requires the next "
                "governed procedure step."
            ),
    }

    assert result.execution_identity.model_dump(
        mode="json"
    ) == {
        "workflow_id":
            "wf-next-001",

        "alert_id":
            "ALT-NEXT-001",

        "correlation_id":
            "corr-next-001",
    }

    assert result.operational_context.model_dump(
        mode="json"
    ) == {
        "alert_id":
            "ALT-NEXT-001",

        "affected_resource":
            "vm-authoritative-01",

        "resource_type":
            "Microsoft.Compute/virtualMachines",

        "service":
            "Azure Virtual Machines",

        "environment":
            "sandbox",

        "incident_origin":
            "observed",

        "subscription_id":
            "sub-next-001",

        "resource_group":
            "rg-next-001",

        "vm_name":
            "vm-authoritative-01",

        "tenant_id":
            "tenant-next-001",

        "correlation_id":
            "corr-next-001",
    }


def test_builder_rejects_resolved_decision():
    builder = load_builder()

    with pytest.raises(
        ValueError,
        match="CONTINUE",
    ):
        builder(
            outcome=make_outcome(
                next_action=NextAction.RESOLVED
            ),
            continuation=(
                make_continuation_context()
            ),
        )


def test_builder_rejects_repeat_decision():
    builder = load_builder()

    with pytest.raises(
        ValueError,
        match="CONTINUE",
    ):
        builder(
            outcome=make_outcome(
                next_action=NextAction.REPEAT
            ),
            continuation=(
                make_continuation_context()
            ),
        )


def test_builder_rejects_continue_when_no_later_step_exists():
    builder = load_builder()

    state = make_runtime_state()

    state.current_step = 3
    state.total_steps = 3

    with pytest.raises(
        ValueError,
        match="posterior",
    ):
        builder(
            outcome=make_outcome(
                state=state,
            ),
            continuation=(
                make_continuation_context()
            ),
        )


def test_builder_rejects_procedure_not_found_snapshot():
    builder = load_builder()

    with pytest.raises(
        ValueError,
        match="admission",
    ):
        builder(
            outcome=make_outcome(),
            continuation=(
                make_continuation_context(
                    procedure_found=False
                )
            ),
        )


def test_builder_rejects_non_exact_procedure_match_snapshot():
    builder = load_builder()

    with pytest.raises(
        ValueError,
        match="admission",
    ):
        builder(
            outcome=make_outcome(),
            continuation=(
                make_continuation_context(
                    procedure_match="partial"
                )
            ),
        )


def test_builder_rejects_non_eligible_snapshot():
    builder = load_builder()

    with pytest.raises(
        ValueError,
        match="admission",
    ):
        builder(
            outcome=make_outcome(),
            continuation=(
                make_continuation_context(
                    execution_eligible=False
                )
            ),
        )


def test_builder_rejects_continue_with_inconsistent_transitioned_state():
    builder = load_builder()

    state = make_runtime_state()

    state.step_status = (
        StepStatus.WAITING_VALIDATION
    )

    state.workflow_status = (
        WorkflowStatus.WAITING_VALIDATION
    )

    with pytest.raises(
        ValueError,
        match="transicion",
    ):
        builder(
            outcome=make_outcome(
                state=state,
            ),
            continuation=(
                make_continuation_context()
            ),
        )


def test_builder_is_pure_and_does_not_mutate_authority_inputs():
    builder = load_builder()

    outcome = make_outcome()

    continuation = (
        make_continuation_context()
    )

    outcome_before = outcome.model_dump(
        mode="python"
    )

    continuation_before = (
        continuation.model_dump(
            mode="python"
        )
    )

    builder(
        outcome=outcome,
        continuation=continuation,
    )

    assert (
        outcome.model_dump(
            mode="python"
        )
        == outcome_before
    )

    assert (
        continuation.model_dump(
            mode="python"
        )
        == continuation_before
    )
