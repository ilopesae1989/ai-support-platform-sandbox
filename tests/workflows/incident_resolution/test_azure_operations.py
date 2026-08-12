import pytest

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
    NextAction,
    OperationAction,
    OperationKind,
    ResolvedParameter,
)

from src.workflows.incident_resolution.azure_operations import (
    build_azure_operation_request,
)


APPROVAL_ID = (
    "apr-11111111-1111-4111-"
    "8111-111111111111"
)

READ_DESCRIPTION = (
    "Consultar el Resource Group rg-test."
)

WRITE_DESCRIPTION = (
    "Actualizar el Resource Group rg-test."
)


def create_step(
    *,
    approved: bool = True,
    domain: str = "azure",
    operation_kind: OperationKind = (
        OperationKind.READ
    ),
    operation_action: OperationAction | None = None,
    capability_id: str | None = None,
    hitl_required: bool | None = None,
    next_action: NextAction = (
        NextAction.EXECUTE_STEP
    ),
    description: str = (
        READ_DESCRIPTION
    ),
) -> ApprovedProcedureStep:
    return ApprovedProcedureStep(
        workflow_id="wf-001",

        approval_id=(
            APPROVAL_ID
        ),

        alert_id="alert-001",

        correlation_id="corr-001",

        conversation_id="conv-001",

        procedure_id="proc-001",

        procedure_version="1",

        current_step=1,

        step_id="step-001",

        description=(
            description
        ),

        operation_domain=domain,

        operation_kind=operation_kind,

        operation_action=(
            operation_action
        ),

        capability_id=(
            capability_id
        ),

        hitl_required=(
            hitl_required
        ),

        next_action=next_action,

        target_resource=(
            "/subscriptions/sub-001/"
            "resourceGroups/rg-test"
        ),

        required_parameters=[
            "resource_group",
        ],

        resolved_parameters=[
            ResolvedParameter(
                name="resource_group",

                value="rg-test",

                source=(
                    "normalized_alert."
                    "resource_group"
                ),
            )
        ],

        approved=approved,
    )


def test_approved_azure_read_builds_request():
    step = create_step()

    request = (
        build_azure_operation_request(
            step
        )
    )

    assert (
        request.workflow_id
        == step.workflow_id
    )

    assert (
        request.approval_id
        == step.approval_id
    )

    assert (
        request.alert_id
        == step.alert_id
    )

    assert (
        request.correlation_id
        == step.correlation_id
    )

    assert (
        request.conversation_id
        == step.conversation_id
    )

    assert (
        request.procedure_id
        == step.procedure_id
    )

    assert (
        request.procedure_version
        == step.procedure_version
    )

    assert (
        request.current_step
        == step.current_step
    )

    assert (
        request.step_id
        == step.step_id
    )

    assert (
        request.description
        == READ_DESCRIPTION
    )

    assert (
        request.description
        == step.description
    )

    assert (
        request.operation_domain
        == "azure"
    )

    assert (
        request.operation_kind
        == OperationKind.READ
    )

    assert (
        request.next_action
        == NextAction.EXECUTE_STEP
    )

    assert (
        request.target_resource
        == step.target_resource
    )

    assert (
        request.required_parameters
        == [
            "resource_group",
        ]
    )

    assert (
        request.resolved_parameters
        == [
            ResolvedParameter(
                name="resource_group",

                value="rg-test",

                source=(
                    "normalized_alert."
                    "resource_group"
                ),
            )
        ]
    )


def test_approved_azure_write_builds_request():
    step = create_step(
        operation_kind=(
            OperationKind.WRITE
        ),

        operation_action=(
            OperationAction.VM_START
        ),

        capability_id=(
            "azure.vm.start"
        ),

        hitl_required=True,

        description=(
            WRITE_DESCRIPTION
        ),
    )

    request = (
        build_azure_operation_request(
            step
        )
    )

    assert (
        request.operation_kind
        == OperationKind.WRITE
    )

    assert (
        request.operation_action
        == OperationAction.VM_START
    )

    assert (
        request.capability_id
        == "azure.vm.start"
    )

    assert (
        request.hitl_required
        is True
    )

    assert (
        request.description
        == WRITE_DESCRIPTION
    )


def test_write_without_capability_id_is_rejected():
    step = create_step(
        operation_kind=(
            OperationKind.WRITE
        ),

        operation_action=(
            OperationAction.VM_START
        ),

        hitl_required=True,

        description=(
            WRITE_DESCRIPTION
        ),
    )

    with pytest.raises(
        ValueError,
        match="capability_id",
    ):
        build_azure_operation_request(
            step
        )


def test_write_without_required_hitl_is_rejected():
    step = create_step(
        operation_kind=(
            OperationKind.WRITE
        ),

        operation_action=(
            OperationAction.VM_START
        ),

        capability_id=(
            "azure.vm.start"
        ),

        hitl_required=False,

        description=(
            WRITE_DESCRIPTION
        ),
    )

    with pytest.raises(
        ValueError,
        match="hitl_required=True",
    ):
        build_azure_operation_request(
            step
        )


def test_write_without_operation_action_is_rejected():
    step = create_step(
        operation_kind=(
            OperationKind.WRITE
        ),

        capability_id=(
            "azure.vm.start"
        ),

        hitl_required=True,

        description=(
            WRITE_DESCRIPTION
        ),
    )

    with pytest.raises(
        ValueError,
        match="operation_action",
    ):
        build_azure_operation_request(
            step
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
        match="dominio azure",
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
        operation_kind=(
            operation_kind
        ),
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