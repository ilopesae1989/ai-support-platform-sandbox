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
    WorkflowStatus,
)

from src.runtime.procedure.workflow import (
    ProcedureApprovalExecutor,
    build_approved_procedure_step,
)

from src.workflows.incident_resolution.azure_operations import (
    build_azure_operation_request,
)

from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
)

from src.workflows.incident_resolution.executors.operation_lifecycle import (
    _validate_request_against_runtime,
)

from src.workflows.incident_resolution.pre_call_security import (
    PreCallSecurityError,
    PreCallSecurityVerifier,
)


SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-a9ae-e9e89b5ad172"
)

RESOURCE_GROUP = (
    "rg-icenter-sandbox-vm-demo"
)

VM_NAME = (
    "vm-icenter-sbx-demo-01"
)

TARGET_RESOURCE = (
    f"/subscriptions/{SUBSCRIPTION_ID}/"
    f"resourceGroups/{RESOURCE_GROUP}/"
    "providers/Microsoft.Compute/"
    f"virtualMachines/{VM_NAME}"
)


def create_runtime_state():
    return ProcedureRuntimeState(
        workflow_id="wf-vm-start-001",
        approval_id="apr-vm-start-001",

        alert_id="ALT-VM-START-001",
        correlation_id="corr-vm-start-001",

        procedure=ProcedureReference(
            id="NTTSY-SBX-AZ-VM-001",
            name="Recuperación de VM detenida",
            version="1.0",
        ),

        total_steps=1,
        current_step=1,

        step=ProcedureStep(
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

            target_resource=TARGET_RESOURCE,

            required_parameters=[
                "subscription_id",
                "resource_group",
                "vm_name",
            ],
        ),

        resolved_parameters=[
            ResolvedParameter(
                name="subscription_id",
                value=SUBSCRIPTION_ID,
                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            ),
            ResolvedParameter(
                name="resource_group",
                value=RESOURCE_GROUP,
                source=(
                    "normalized_alert."
                    "resource_group"
                ),
            ),
            ResolvedParameter(
                name="vm_name",
                value=VM_NAME,
                source=(
                    "normalized_alert."
                    "vm_name"
                ),
            ),
        ],

        workflow_status=(
            WorkflowStatus.RUNNING
        ),

        step_status=(
            StepStatus.APPROVED
        ),

        approval_status=(
            ApprovalStatus.APPROVED
        ),
    )


def test_vm_start_action_survives_all_pre_dispatch_boundaries():
    state = create_runtime_state()

    approval_request = (
        ProcedureApprovalExecutor
        ._build_approval_request(
            state
        )
    )

    assert (
        approval_request.operation_action
        == "vm_start"
    )

    approved_step = (
        build_approved_procedure_step(
            state
        )
    )

    assert (
        approved_step.operation_action
        == OperationAction.VM_START
    )

    candidate = (
        build_azure_operation_request(
            approved_step
        )
    )

    assert (
        candidate.operation_action
        == OperationAction.VM_START
    )

    verified = (
        PreCallSecurityVerifier.verify(
            approved_step=approved_step,
            candidate=candidate,
        )
    )

    assert (
        verified.operation_action
        == OperationAction.VM_START
    )

    _validate_request_against_runtime(
        verified,
        state,
    )

    prompt = (
        AzureOperationsExecutor
        ._build_prompt(
            verified
        )
    )

    assert "vm_start" in prompt
    assert "execute_step" in prompt


def test_pre_call_rejects_operation_action_substitution():
    """
    Una operación aprobada como vm_start no puede
    transformarse después del HITL en vm_stop.

    model_copy(update=...) se usa deliberadamente
    para simular una modificación posterior que evita
    la validación normal de Pydantic.
    """

    state = create_runtime_state()

    approved_step = (
        build_approved_procedure_step(
            state
        )
    )

    assert (
        approved_step.operation_action
        == OperationAction.VM_START
    )

    candidate = (
        build_azure_operation_request(
            approved_step
        )
    )

    tampered = candidate.model_copy(
        update={
            "operation_action":
                "vm_stop",
        },
        deep=True,
    )

    with pytest.raises(
        PreCallSecurityError,
        match="operation_action",
    ):
        PreCallSecurityVerifier.verify(
            approved_step=approved_step,
            candidate=tampered,
        )


def test_operation_start_rejects_operation_action_different_from_runtime():
    """
    Una solicitud ya verificada no puede perder ni
    modificar operation_action después de PreCall.

    Se utiliza model_construct() deliberadamente
    para representar una corrupción posterior a la
    validación normal.

    El payload conserva las instancias tipadas reales
    del request verificado para que el test no genere
    ruido de serialización ajeno al ataque probado.
    """

    state = create_runtime_state()

    approved_step = (
        build_approved_procedure_step(
            state
        )
    )

    candidate = (
        build_azure_operation_request(
            approved_step
        )
    )

    verified = (
        PreCallSecurityVerifier.verify(
            approved_step=approved_step,
            candidate=candidate,
        )
    )

    assert (
        verified.operation_action
        == OperationAction.VM_START
    )

    #
    # Conservamos los valores tipados originales.
    #
    # No utilizamos model_dump() aquí porque queremos
    # construir el objeto adversarial sin convertir
    # VerifiedResolvedParameter en dicts.
    #
    payload = {
        field_name: getattr(
            verified,
            field_name,
        )
        for field_name
        in type(
            verified
        ).model_fields
    }

    #
    # Corrupción posterior a PreCall.
    #
    # None es válido para el contrato transitorio
    # actual, pero NO coincide con la operación
    # vm_start que mantiene el runtime autoritativo.
    #
    payload[
        "operation_action"
    ] = None

    tampered_verified = (
        type(
            verified
        ).model_construct(
            **payload
        )
    )

    with pytest.raises(
        ValueError,
        match="operation_action",
    ):
        _validate_request_against_runtime(
            tampered_verified,
            state,
        )