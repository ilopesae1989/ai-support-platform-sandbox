import pytest

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
    NextAction,
    OperationKind,
)
from src.workflows.incident_resolution.azure_operations import (
    build_azure_operation_request,
)


def create_step(
    *,
    approved: bool = True,
    domain: str = "azure",
    operation_kind: OperationKind = OperationKind.READ,
    next_action: NextAction = NextAction.EXECUTE_STEP,
) -> ApprovedProcedureStep:
    return ApprovedProcedureStep(
        workflow_id="wf-001",
        alert_id="alert-001",
        conversation_id="conv-001",
        procedure_id="proc-001",
        procedure_version="1",
        current_step=1,
        step_id="step-001",
        operation_domain=domain,
        operation_kind=operation_kind,
        next_action=next_action,
        target_resource=(
            "/subscriptions/sub-001/"
            "resourceGroups/rg-test"
        ),
        required_parameters=[
            "resource_group",
        ],
        approved=approved,
    )


def test_approved_azure_read_builds_request():
    step = create_step()

    request = build_azure_operation_request(
        step
    )

    assert request.workflow_id == "wf-001"
    assert request.alert_id == "alert-001"

    assert request.procedure_id == "proc-001"
    assert request.procedure_version == "1"

    assert request.current_step == 1
    assert request.step_id == "step-001"

    assert (
        request.operation_kind
        == OperationKind.READ
    )

    assert request.target_resource is not None

    assert request.required_parameters == [
        "resource_group",
    ]


def test_approved_azure_write_builds_request():
    step = create_step(
        operation_kind=OperationKind.WRITE,
    )

    request = build_azure_operation_request(
        step
    )

    assert (
        request.operation_kind
        == OperationKind.WRITE
    )


def test_unapproved_step_is_rejected():
    step = create_step(
        approved=False,
    )

    with pytest.raises(
        ValueError,
        match="no aprobado",
    ):
        build_azure_operation_request(
            step
        )


def test_non_azure_domain_is_rejected():
    step = create_step(
        domain="database",
    )

    with pytest.raises(
        ValueError,
        match="dominio Azure",
    ):
        build_azure_operation_request(
            step
        )


@pytest.mark.parametrize(
    "operation_kind",
    [
        OperationKind.WAIT,
        OperationKind.HUMAN,
        OperationKind.NONE,
    ],
)
def test_non_operational_kind_is_rejected(
    operation_kind,
):
    step = create_step(
        operation_kind=operation_kind,
    )

    with pytest.raises(
        ValueError,
        match="read o write",
    ):
        build_azure_operation_request(
            step
        )


@pytest.mark.parametrize(
    "next_action",
    [
        NextAction.CONTINUE,
        NextAction.REPEAT,
        NextAction.WAIT,
        NextAction.RESOLVED,
        NextAction.ESCALATE,
        NextAction.BLOCKED,
    ],
)
def test_non_execute_step_is_rejected(
    next_action,
):
    step = create_step(
        next_action=next_action,
    )

    with pytest.raises(
        ValueError,
        match="execute_step",
    ):
        build_azure_operation_request(
            step
        )