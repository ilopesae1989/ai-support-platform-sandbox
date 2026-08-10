import pytest

from src.runtime.procedure.models import (
    ApprovalStatus,
    NextAction,
    OperationKind,
    ProcedureExecutionResult,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    ResolvedParameter,
    StepEvidence,
    StepStatus,
    WorkflowStatus,
)

from src.runtime.procedure.runtime import (
    ProcedureRuntime,
)


def make_state() -> ProcedureRuntimeState:
    return ProcedureRuntimeState(
        workflow_id="wf-transition-001",

        approval_id="apr-transition-001",

        alert_id="ALT-TRANSITION-001",

        correlation_id="corr-transition-001",

        conversation_id="conv-transition-001",

        procedure=ProcedureReference(
            id="NTTSY-TRANSITION-001",
            name="Procedure Transition Test",
            version="1.0",
        ),

        total_steps=2,

        current_step=1,

        step=ProcedureStep(
            id="1",

            description=(
                "Validate current state."
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
                "Expected state is visible."
            ),

            verification=(
                "Validate returned state."
            ),
        ),

        resolved_parameters=[
            ResolvedParameter(
                name="subscription_id",

                value=(
                    "557fdabc-f3b6-4c24-"
                    "a9ae-e9e89b5ad172"
                ),

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
            success=True,

            result={
                "operation_id":
                    "op-transition-001"
            },

            error=None,
        ),
    )


def make_verification() -> StepEvidence:
    return StepEvidence(
        success=True,

        result={
            "operation_id":
                "op-transition-001",

            "validation_status":
                "satisfied",

            "proposed_next_action":
                "continue",
        },

        error=None,
    )


def test_verification_result_can_be_registered_once():
    runtime = ProcedureRuntime()

    state = make_state()

    verification = make_verification()

    result = (
        runtime.register_verification_result(
            state,
            verification,
        )
    )

    assert (
        result.verification_result
        == verification
    )


def test_verification_replay_is_rejected():
    runtime = ProcedureRuntime()

    state = make_state()

    runtime.register_verification_result(
        state,
        make_verification(),
    )

    with pytest.raises(
        ValueError,
        match="validación",
    ):
        runtime.register_verification_result(
            state,
            make_verification(),
        )


def test_verification_requires_waiting_validation():
    runtime = ProcedureRuntime()

    state = make_state()

    state.step_status = (
        StepStatus.RUNNING
    )

    with pytest.raises(
        ValueError,
        match="waiting_validation",
    ):
        runtime.register_verification_result(
            state,
            make_verification(),
        )


def test_decision_requires_waiting_validation():
    runtime = ProcedureRuntime()

    state = make_state()

    state.verification_result = (
        make_verification()
    )

    state.step_status = (
        StepStatus.RUNNING
    )

    with pytest.raises(
        ValueError,
        match="waiting_validation",
    ):
        runtime.apply_procedure_decision(
            state,

            ProcedureExecutionResult(
                next_action=(
                    NextAction.CONTINUE
                )
            ),
        )


def test_decision_requires_verification_result():
    runtime = ProcedureRuntime()

    state = make_state()

    assert (
        state.verification_result
        is None
    )

    with pytest.raises(
        ValueError,
        match="validación",
    ):
        runtime.apply_procedure_decision(
            state,

            ProcedureExecutionResult(
                next_action=(
                    NextAction.CONTINUE
                )
            ),
        )


def test_repeat_invalidates_previous_authorization():
    runtime = ProcedureRuntime()

    state = make_state()

    runtime.register_verification_result(
        state,
        StepEvidence(
            success=False,

            result={
                "operation_id":
                    "op-transition-001",

                "validation_status":
                    "not_satisfied",

                "proposed_next_action":
                    "repeat",
            },
        ),
    )

    result = (
        runtime.apply_procedure_decision(
            state,

            ProcedureExecutionResult(
                next_action=(
                    NextAction.REPEAT
                )
            ),
        )
    )

    assert result.retry_count == 1

    assert (
        result.step_status
        == StepStatus.PENDING
    )

    assert (
        result.workflow_status
        == WorkflowStatus.RUNNING
    )

    #
    # Nueva ejecución => nueva autorización.
    #
    assert result.approval_id is None

    assert (
        result.approval_status
        == ApprovalStatus.PENDING
    )

    #
    # Nunca se reutiliza resultado/evidencia
    # de la operación anterior.
    #
    assert result.operation_result is None

    assert (
        result.verification_result
        is None
    )

    #
    # Los parámetros deben resolverse de nuevo
    # para la nueva operación concreta.
    #
    assert result.resolved_parameters == []
