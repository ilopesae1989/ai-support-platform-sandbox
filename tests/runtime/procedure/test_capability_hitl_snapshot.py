import pytest

from src.runtime.procedure.models import (
    ApprovalStatus,
    OperationAction,
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    ResolvedParameter,
    StepStatus,
)

from src.runtime.procedure.runtime import (
    ProcedureRuntime,
)

from src.runtime.procedure.workflow import (
    ProcedureApprovalExecutor,
    build_approved_procedure_step,
)


def create_bound_write_state(
) -> ProcedureRuntimeState:

    return ProcedureRuntimeState(
        workflow_id=(
            "wf-capability-hitl-001"
        ),

        alert_id=(
            "ALT-CAPABILITY-HITL-001"
        ),

        correlation_id=(
            "corr-capability-hitl-001"
        ),

        approval_id=(
            "approval-capability-hitl-001"
        ),

        procedure=ProcedureReference(
            id="TEST-PROC-VM-START",
            name="Test VM Start",
            version="1.0",
        ),

        total_steps=2,

        current_step=2,

        step=ProcedureStep(
            id="2",

            description=(
                "Arrancar la máquina virtual "
                "autorizada."
            ),

            step_type=(
                "technical_operation"
            ),

            operation_domain="azure",

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

            target_resource=(
                "/subscriptions/sub-test/"
                "resourceGroups/rg-test/"
                "providers/Microsoft.Compute/"
                "virtualMachines/vm-test"
            ),

            required_parameters=[
                "subscription_id",
                "resource_group",
                "vm_name",
            ],
        ),

        resolved_parameters=[
            ResolvedParameter(
                name="subscription_id",
                value="sub-test",
                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            ),

            ResolvedParameter(
                name="resource_group",
                value="rg-test",
                source=(
                    "normalized_alert."
                    "resource_group"
                ),
            ),

            ResolvedParameter(
                name="vm_name",
                value="vm-test",
                source=(
                    "normalized_alert."
                    "vm_name"
                ),
            ),
        ],
    )


def test_bound_write_capability_requires_hitl():
    runtime = (
        ProcedureRuntime()
    )

    state = (
        create_bound_write_state()
    )

    assert (
        runtime.requires_human_approval(
            state
        )
        is True
    )


def test_governed_write_cannot_disable_hitl():
    runtime = (
        ProcedureRuntime()
    )

    state = (
        create_bound_write_state()
    )

    state.step.hitl_required = False

    with pytest.raises(
        ValueError,
        match="hitl_required=True",
    ):
        runtime.requires_human_approval(
            state
        )


def test_hitl_policy_cannot_exist_without_capability():
    runtime = (
        ProcedureRuntime()
    )

    state = (
        create_bound_write_state()
    )

    state.step.capability_id = None

    with pytest.raises(
        ValueError,
        match="capability_id",
    ):
        runtime.requires_human_approval(
            state
        )


def test_approval_request_freezes_capability_identity():
    state = (
        create_bound_write_state()
    )

    request = (
        ProcedureApprovalExecutor
        ._build_approval_request(
            state
        )
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
        request.operation_action
        == "vm_start"
    )


def test_approved_step_preserves_capability_identity():
    state = (
        create_bound_write_state()
    )

    state.approval_status = (
        ApprovalStatus.APPROVED
    )

    state.step_status = (
        StepStatus.APPROVED
    )

    approved = (
        build_approved_procedure_step(
            state
        )
    )

    assert (
        approved.capability_id
        == "azure.vm.start"
    )

    assert (
        approved.hitl_required
        is True
    )

    assert (
        approved.operation_action
        == OperationAction.VM_START
    )
