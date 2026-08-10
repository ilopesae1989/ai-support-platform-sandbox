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
from src.runtime.procedure.runtime import ProcedureRuntime


@pytest.fixture
def runtime() -> ProcedureRuntime:
    return ProcedureRuntime()


@pytest.fixture
def always_on_state() -> ProcedureRuntimeState:
    return ProcedureRuntimeState(
        workflow_id="wf-test-001",
        conversation_id="conv-test-001",
        alert_id="ALT-SQL-AG-001",
        procedure=ProcedureReference(
            id="NTTSY-PRO-020",
            name="Alertas SQL Server",
            version="v1.1",
        ),
        total_steps=5,
        current_step=1,
        step=ProcedureStep(
            id="1",
            description=(
                "Comprobar el estado actual de la réplica "
                "de Always On."
            ),
            step_type="validation",
            operation_domain="database",
            operation_kind=OperationKind.READ,
            target_resource="SQLPROD01",
            required_parameters=[],
            preconditions=[],
            expected_result=(
                "El estado actual de sincronización queda identificado."
            ),
            verification=(
                "Validar el estado mediante el mecanismo "
                "indicado en el procedimiento."
            ),
        ),
    )


def test_initial_state(always_on_state):
    assert always_on_state.workflow_status == WorkflowStatus.INITIALIZED
    assert always_on_state.step_status == StepStatus.PENDING
    assert always_on_state.approval_status == ApprovalStatus.PENDING


def test_read_operation_requires_approval(
    runtime,
    always_on_state,
):
    state = runtime.prepare_current_step(always_on_state)

    assert state.workflow_status == WorkflowStatus.WAITING_HUMAN
    assert state.step_status == StepStatus.WAITING_APPROVAL
    assert state.approval_status == ApprovalStatus.PENDING


def test_approval_allows_execution(
    runtime,
    always_on_state,
):
    state = runtime.prepare_current_step(always_on_state)

    state = runtime.register_approval(
        state,
        approved=True,
    )

    assert state.workflow_status == WorkflowStatus.RUNNING
    assert state.step_status == StepStatus.APPROVED
    assert state.approval_status == ApprovalStatus.APPROVED


def test_rejection_blocks_workflow(
    runtime,
    always_on_state,
):
    state = runtime.prepare_current_step(always_on_state)

    state = runtime.register_approval(
        state,
        approved=False,
    )

    assert state.workflow_status == WorkflowStatus.BLOCKED
    assert state.step_status == StepStatus.REJECTED
    assert state.approval_status == ApprovalStatus.REJECTED


def test_operation_cannot_start_without_approval(
    runtime,
    always_on_state,
):
    with pytest.raises(ValueError):
        runtime.mark_operation_started(always_on_state)


def test_operation_success_waits_for_procedure_validation(
    runtime,
    always_on_state,
):
    state = runtime.prepare_current_step(always_on_state)
    state = runtime.register_approval(state, approved=True)
    state = runtime.mark_operation_started(state)

    state = runtime.register_operation_result(
        state,
        StepEvidence(
            success=True,
            result={
                "availability_group": "AG-PROD",
                "synchronization_state": "NOT_SYNCHRONIZING",
            },
        ),
    )

    assert state.workflow_status == WorkflowStatus.WAITING_VALIDATION
    assert state.step_status == StepStatus.WAITING_VALIDATION
    assert state.operation_result is not None


def test_continue_decision_marks_step_succeeded(
    runtime,
    always_on_state,
):
    state = runtime.prepare_current_step(always_on_state)
    state = runtime.register_approval(state, approved=True)
    state = runtime.mark_operation_started(state)

    state = runtime.register_operation_result(
        state,
        StepEvidence(
            success=True,
            result={"state": "NOT_SYNCHRONIZING"},
        ),
    )

    state = runtime.register_verification_result(
        state,
        StepEvidence(
            success=True,
            result={
                "validation_status": "satisfied",
                "proposed_next_action": "continue",
            },
        ),
    )

    state = runtime.apply_procedure_decision(
        state,
        ProcedureExecutionResult(
            next_action=NextAction.CONTINUE,
        ),
    )

    assert state.step_status == StepStatus.SUCCEEDED
    assert state.workflow_status == WorkflowStatus.RUNNING


def test_resolved_decision_finishes_workflow(
    runtime,
    always_on_state,
):
    state = runtime.prepare_current_step(always_on_state)
    state = runtime.register_approval(state, approved=True)
    state = runtime.mark_operation_started(state)

    state = runtime.register_operation_result(
        state,
        StepEvidence(
            success=True,
            result={"state": "SYNCHRONIZED"},
        ),
    )

    state = runtime.register_verification_result(
        state,
        StepEvidence(
            success=True,
            result={
                "validation_status": "satisfied",
                "proposed_next_action": "resolved",
            },
        ),
    )

    state = runtime.apply_procedure_decision(
        state,
        ProcedureExecutionResult(
            next_action=NextAction.RESOLVED,
        ),
    )

    assert state.workflow_status == WorkflowStatus.RESOLVED


def test_escalation_decision(
    runtime,
    always_on_state,
):
    state = runtime.prepare_current_step(always_on_state)
    state = runtime.register_approval(state, approved=True)
    state = runtime.mark_operation_started(state)

    state = runtime.register_operation_result(
        state,
        StepEvidence(
            success=False,
            error="Replica remains unhealthy",
        ),
    )

    state = runtime.register_verification_result(
        state,
        StepEvidence(
            success=False,
            result={
                "validation_status": "not_satisfied",
                "proposed_next_action": "escalate",
            },
        ),
    )

    state = runtime.apply_procedure_decision(
        state,
        ProcedureExecutionResult(
            next_action=NextAction.ESCALATE,
            escalation_required=True,
            escalation_team="Arquitectura",
            escalation_criteria="Persistencia del fallo.",
        ),
    )

    assert state.workflow_status == WorkflowStatus.ESCALATION_REQUIRED
    assert state.escalation_required is True
    assert state.escalation_team == "Arquitectura"