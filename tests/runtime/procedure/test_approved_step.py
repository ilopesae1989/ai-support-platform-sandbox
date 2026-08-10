import pytest

from src.runtime.procedure.models import (
    ApprovalStatus,
    NextAction,
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    StepStatus,
    WorkflowStatus,
)
from src.runtime.procedure.workflow import (
    build_approved_procedure_step,
)


def create_state() -> ProcedureRuntimeState:
    return ProcedureRuntimeState(
        workflow_id="wf-001",
        alert_id="ALT-001",
        procedure=ProcedureReference(
            id="PROC-001",
            name="Test procedure",
            version="v1.0",
        ),
        total_steps=1,
        current_step=1,
        step=ProcedureStep(
            id="1",
            description="Consultar estado.",
            step_type="validation",
            operation_domain="database",
            operation_kind=OperationKind.READ,
            target_resource="SQL01",
            required_parameters=[
                "instance_name",
            ],
        ),
    )


def test_approved_state_builds_approved_step():
    state = create_state()

    state.resolved_parameters = [
        {
            "name": "instance_name",
            "value": "prod-sql",
            "source": "manual",
        }
    ]

    state.step_status = (
        StepStatus.APPROVED
    )

    state.approval_status = (
        ApprovalStatus.APPROVED
    )

    state.workflow_status = (
        WorkflowStatus.RUNNING
    )

    result = (
        build_approved_procedure_step(
            state
        )
    )

    assert result.approved is True

    assert (
        result.workflow_id
        == "wf-001"
    )

    assert (
        result.alert_id
        == "ALT-001"
    )

    assert (
        result.procedure_id
        == "PROC-001"
    )

    assert (
        result.procedure_version
        == "v1.0"
    )

    assert (
        result.current_step
        == 1
    )

    assert (
        result.step_id
        == "1"
    )

    assert (
        result.operation_domain
        == "database"
    )

    assert (
        result.operation_kind
        == OperationKind.READ
    )

    assert (
        result.next_action
        == NextAction.EXECUTE_STEP
    )

    assert (
        result.target_resource
        == "SQL01"
    )

    assert (
        result.required_parameters
        == [
            "instance_name",
        ]
    )


def test_pending_state_cannot_build_approved_step():
    state = create_state()

    with pytest.raises(
        ValueError,
        match=(
            "sin aprobación humana válida"
        ),
    ):
        build_approved_procedure_step(
            state
        )


def test_rejected_state_cannot_build_approved_step():
    state = create_state()

    state.step_status = (
        StepStatus.REJECTED
    )

    state.approval_status = (
        ApprovalStatus.REJECTED
    )

    state.workflow_status = (
        WorkflowStatus.BLOCKED
    )

    with pytest.raises(
        ValueError
    ):
        build_approved_procedure_step(
            state
        )