from __future__ import annotations

from src.runtime.procedure.identity import (
    create_operation_id,
)

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
    NextAction,
    OperationKind,
)

from .azure_operations_models import (
    AzureOperationRequest,
)


def _validate_parameter_binding(
    step: ApprovedProcedureStep,
) -> None:
    required = list(
        step.required_parameters
    )

    resolved_names = [
        parameter.name
        for parameter
        in step.resolved_parameters
    ]

    if (
        len(required)
        != len(set(required))
    ):
        raise ValueError(
            "El paso aprobado contiene "
            "required_parameters duplicados."
        )

    if (
        len(resolved_names)
        != len(set(resolved_names))
    ):
        raise ValueError(
            "El paso aprobado contiene "
            "resolved_parameters duplicados."
        )

    if required != resolved_names:
        raise ValueError(
            "Los resolved_parameters del paso "
            "aprobado no coinciden exactamente "
            "con required_parameters."
        )

    for parameter in (
        step.resolved_parameters
    ):
        if parameter.name == "":
            raise ValueError(
                "Existe un parámetro resuelto "
                "sin nombre."
            )

        if parameter.value == "":
            raise ValueError(
                "Existe un parámetro resuelto "
                "sin valor."
            )

        if parameter.source == "":
            raise ValueError(
                "Existe un parámetro resuelto "
                "sin origen autoritativo."
            )


def build_azure_operation_request(
    step: ApprovedProcedureStep,
) -> AzureOperationRequest:
    if step.approved is not True:
        raise ValueError(
            "No puede construirse una operación Azure "
            "desde un paso no aprobado."
        )

    if not step.approval_id:
        raise ValueError(
            "La operación Azure aprobada no contiene "
            "approval_id."
        )

    if (
        not step.description
        or not step.description.strip()
    ):
        raise ValueError(
            "La operación Azure aprobada no contiene "
            "description válida."
        )

    if (
        step.operation_domain
        != "azure"
    ):
        raise ValueError(
            "El paso aprobado no pertenece "
            "exactamente al dominio azure."
        )

    if (
        step.next_action
        != NextAction.EXECUTE_STEP
    ):
        raise ValueError(
            "La operación Azure requiere "
            "next_action=execute_step."
        )

    if step.operation_kind not in {
        OperationKind.READ,
        OperationKind.WRITE,
    }:
        raise ValueError(
            "Azure Operations sólo admite "
            "operaciones read o write."
        )

    _validate_parameter_binding(
        step
    )

    operation_id = (
        create_operation_id(
            workflow_id=(
                step.workflow_id
            ),

            approval_id=(
                step.approval_id
            ),

            alert_id=(
                step.alert_id
            ),

            procedure_id=(
                step.procedure_id
            ),

            current_step=(
                step.current_step
            ),

            step_id=(
                step.step_id
            ),
        )
    )

    return AzureOperationRequest(
        operation_id=(
            operation_id
        ),

        workflow_id=(
            step.workflow_id
        ),

        approval_id=(
            step.approval_id
        ),

        alert_id=(
            step.alert_id
        ),

        correlation_id=(
            step.correlation_id
        ),

        conversation_id=(
            step.conversation_id
        ),

        procedure_id=(
            step.procedure_id
        ),

        procedure_version=(
            step.procedure_version
        ),

        current_step=(
            step.current_step
        ),

        step_id=(
            step.step_id
        ),

        description=(
            step.description
        ),

        operation_domain=(
            step.operation_domain
        ),

        operation_kind=(
            step.operation_kind
        ),

        operation_action=(
            step.operation_action
        ),

        next_action=(
            step.next_action
        ),

        target_resource=(
            step.target_resource
        ),

        required_parameters=list(
            step.required_parameters
        ),

        resolved_parameters=[
            parameter.model_copy(
                deep=True
            )
            for parameter
            in step.resolved_parameters
        ],
    )