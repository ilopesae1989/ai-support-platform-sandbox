import pytest

from src.agents.contracts import (
    ProcedureValidationResult,
)

from src.runtime.procedure.models import (
    ApprovalStatus,
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    ResolvedParameter,
    StepEvidence,
    StepStatus,
    WorkflowStatus,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)

from src.workflows.incident_resolution.procedure_transition_gate import (
    apply_procedure_validation_transition,
)

from src.workflows.incident_resolution.procedure_validation_models import (
    ProcedureValidationContext,
    ProcedureValidationRequest,
    ProcedureValidationStep,
)


SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)


def make_operation_result() -> OperationResult:
    return OperationResult(
        operation_id="op-gate-001",

        workflow_id="wf-gate-001",

        approval_id="apr-gate-001",

        alert_id="ALT-GATE-001",

        correlation_id="corr-gate-001",

        conversation_id="conv-gate-001",

        procedure_id="NTTSY-GATE-001",

        procedure_version="1.0",

        current_step=1,

        step_id="1",

        operation_domain="azure",

        operation_kind="read",

        next_action="execute_step",

        target_resource="subscription",

        required_parameters=[
            "subscription_id"
        ],

        resolved_parameters=[
            ResolvedParameter(
                name="subscription_id",

                value=SUBSCRIPTION_ID,

                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            )
        ],

        success=True,

        technical_success=None,

        response_text=(
            "Backend invocation completed."
        ),

        error=None,

        evidence=None,
    )


def make_state() -> ProcedureRuntimeState:
    operation_result = (
        make_operation_result()
    )

    return ProcedureRuntimeState(
        workflow_id="wf-gate-001",

        approval_id="apr-gate-001",

        alert_id="ALT-GATE-001",

        correlation_id="corr-gate-001",

        conversation_id="conv-gate-001",

        procedure=ProcedureReference(
            id="NTTSY-GATE-001",

            name="Transition Gate Test",

            version="1.0",
        ),

        total_steps=2,

        current_step=1,

        step=ProcedureStep(
            id="1",

            description=(
                "Read subscription state."
            ),

            step_type="validation",

            operation_domain="azure",

            operation_kind=(
                OperationKind.READ
            ),

            target_resource="subscription",

            required_parameters=[
                "subscription_id"
            ],

            preconditions=[],

            expected_result=(
                "Subscription state is visible."
            ),

            verification=(
                "Validate returned state."
            ),
        ),

        resolved_parameters=[
            ResolvedParameter(
                name="subscription_id",

                value=SUBSCRIPTION_ID,

                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            )
        ],

        workflow_status=(
            WorkflowStatus.WAITING_VALIDATION
        ),

        step_status=(
            StepStatus.WAITING_VALIDATION
        ),

        approval_status=(
            ApprovalStatus.APPROVED
        ),

        operation_result=StepEvidence(
            success=(
                operation_result.success
            ),

            result=(
                operation_result.model_dump(
                    mode="json"
                )
            ),

            error=(
                operation_result.error
            ),
        ),
    )


def make_context(
    *,
    validation_status="satisfied",
    proposed_next_action="continue",
) -> ProcedureValidationContext:
    operation_result = (
        make_operation_result()
    )

    request = ProcedureValidationRequest(
        operation_result=(
            operation_result
        ),

        step=ProcedureValidationStep(
            procedure_id="NTTSY-GATE-001",

            procedure_version="1.0",

            current_step=1,

            step_id="1",

            description=(
                "Read subscription state."
            ),

            expected_result=(
                "Subscription state is visible."
            ),

            verification=(
                "Validate returned state."
            ),
        ),
    )

    result = (
        ProcedureValidationResult
        .model_validate(
            {
                "operation_id":
                    "op-gate-001",

                "validation_status":
                    validation_status,

                "proposed_next_action":
                    proposed_next_action,

                "validation_summary":
                    "Procedure evidence interpreted.",

                "escalation": {
                    "required": False,
                    "team": None,
                    "level": None,
                    "criteria": None,
                },
            }
        )
    )

    return ProcedureValidationContext(
        request=request,
        result=result,
    )


def test_continue_applies_only_after_exact_validation():
    state = make_state()

    original = (
        state.model_dump(
            mode="python"
        )
    )

    result = (
        apply_procedure_validation_transition(
            state=state,
            context=make_context(),
        )
    )

    assert (
        result.step_status
        == StepStatus.SUCCEEDED
    )

    assert (
        result.workflow_status
        == WorkflowStatus.RUNNING
    )

    assert (
        result.verification_result
        is not None
    )

    #
    # El gate trabaja sobre una copia
    # revalidada del estado.
    #
    assert (
        state.model_dump(
            mode="python"
        )
        == original
    )


def test_gate_rejects_wrong_runtime_state():
    state = make_state()

    state.step_status = (
        StepStatus.RUNNING
    )

    with pytest.raises(
        ValueError,
        match="waiting_validation",
    ):
        apply_procedure_validation_transition(
            state=state,
            context=make_context(),
        )


def test_gate_rejects_missing_operation_result():
    state = make_state()

    state.operation_result = None

    with pytest.raises(
        ValueError,
        match="operation_result",
    ):
        apply_procedure_validation_transition(
            state=state,
            context=make_context(),
        )


def test_gate_rejects_operation_result_substitution():
    state = make_state()

    context = make_context()

    substituted = (
        context.request.operation_result
        .model_copy(
            update={
                "workflow_id":
                    "wf-attacker"
            }
        )
    )

    request = ProcedureValidationRequest(
        operation_result=substituted,
        step=context.request.step,
    )

    tampered = ProcedureValidationContext(
        request=request,
        result=context.result,
    )

    with pytest.raises(
        ValueError,
        match="OperationResult",
    ):
        apply_procedure_validation_transition(
            state=state,
            context=tampered,
        )


def test_gate_rejects_step_substitution():
    state = make_state()

    context = make_context()

    substituted_step = (
        ProcedureValidationStep(
            procedure_id="NTTSY-GATE-001",

            procedure_version="1.0",

            current_step=1,

            step_id="1",

            description=(
                "Tampered description."
            ),

            expected_result=(
                "Subscription state is visible."
            ),

            verification=(
                "Validate returned state."
            ),
        )
    )

    request = ProcedureValidationRequest(
        operation_result=(
            context.request.operation_result
        ),

        step=substituted_step,
    )

    tampered = ProcedureValidationContext(
        request=request,
        result=context.result,
    )

    with pytest.raises(
        ValueError,
        match="ProcedureValidationStep",
    ):
        apply_procedure_validation_transition(
            state=state,
            context=tampered,
        )


def test_gate_blocks_validation_replay():
    state = make_state()

    state.verification_result = (
        StepEvidence(
            success=True,

            result={
                "validation_status":
                    "satisfied"
            },
        )
    )

    with pytest.raises(
        ValueError,
        match="replay",
    ):
        apply_procedure_validation_transition(
            state=state,
            context=make_context(),
        )


def test_resolved_requires_satisfied_validation():
    state = make_state()

    context = make_context(
        validation_status="indeterminate",
        proposed_next_action="resolved",
    )

    with pytest.raises(
        ValueError,
        match="resolved",
    ):
        apply_procedure_validation_transition(
            state=state,
            context=context,
        )


def test_repeat_invalidates_old_operation_identity():
    state = make_state()

    context = make_context(
        validation_status="not_satisfied",
        proposed_next_action="repeat",
    )

    result = (
        apply_procedure_validation_transition(
            state=state,
            context=context,
        )
    )

    assert (
        result.step_status
        == StepStatus.PENDING
    )

    assert result.approval_id is None

    assert (
        result.approval_status
        == ApprovalStatus.PENDING
    )

    assert result.operation_result is None

    assert (
        result.verification_result
        is None
    )

    assert result.resolved_parameters == []

    assert result.retry_count == 1
