from src.runtime.procedure.models import (
    OperationAction,
    OperationKind,
    ProcedureStep,
)

from src.workflows.incident_resolution.operation_models import (
    OperationRequest,
)


def test_vm_start_is_canonical_operation_action():
    assert (
        OperationAction.VM_START.value
        == "vm_start"
    )


def test_procedure_step_accepts_vm_start_operation_action():
    step = ProcedureStep(
        id="1",

        description=(
            "Encender la máquina virtual "
            "autorizada."
        ),

        step_type="technical_operation",

        operation_domain="azure",

        operation_kind=(
            OperationKind.WRITE
        ),

        operation_action=(
            OperationAction.VM_START
        ),

        target_resource=(
            "/subscriptions/sub-001/"
            "resourceGroups/rg-demo/"
            "providers/Microsoft.Compute/"
            "virtualMachines/vm-demo"
        ),

        required_parameters=[
            "subscription_id",
            "resource_group",
            "vm_name",
        ],
    )

    assert (
        step.operation_action
        == OperationAction.VM_START
    )


def test_operation_request_preserves_vm_start_action():
    request = OperationRequest(
        operation_id="op-test-001",

        workflow_id="wf-test-001",
        approval_id="apr-test-001",

        alert_id="ALT-VM-001",

        procedure_id="NTTSY-SBX-AZ-VM-001",
        procedure_version="1.0",

        current_step=1,
        step_id="1",

        operation_domain="azure",

        operation_kind=(
            OperationKind.WRITE
        ),

        operation_action=(
            OperationAction.VM_START
        ),

        next_action="execute_step",

        target_resource=(
            "/subscriptions/sub-001/"
            "resourceGroups/rg-demo/"
            "providers/Microsoft.Compute/"
            "virtualMachines/vm-demo"
        ),

        required_parameters=[
            "subscription_id",
            "resource_group",
            "vm_name",
        ],

        resolved_parameters=[],
    )

    assert (
        request.operation_action
        == OperationAction.VM_START
    )


def test_existing_operations_may_temporarily_omit_operation_action():
    step = ProcedureStep(
        id="1",

        description=(
            "Consultar Resource Groups."
        ),

        step_type="validation",

        operation_domain="azure",

        operation_kind=(
            OperationKind.READ
        ),

        target_resource="subscription",

        required_parameters=[
            "subscription_id",
        ],
    )

    assert (
        step.operation_action
        is None
    )