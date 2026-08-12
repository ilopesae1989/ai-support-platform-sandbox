from __future__ import annotations

from src.runtime.procedure.identity import (
    create_operation_id,
)

from src.runtime.procedure.models import (
    ApprovalStatus,
    NextAction,
    ProcedureRuntimeState,
    StepStatus,
    WorkflowStatus,
)

from .operation_models import (
    OperationResult,
)


def _resolved_parameter_snapshot(
    parameters,
) -> list[dict]:
    """
    Representación comparable de parámetros
    manteniendo name/value/source.
    """

    return [
        parameter.model_dump(
            mode="python"
        )
        for parameter
        in parameters
    ]


def _revalidate_result(
    result: OperationResult,
) -> OperationResult:
    """
    Reconstruye el resultado a través del contrato
    Pydantic completo.

    Esto cierra objetos que hayan podido construirse
    mediante model_construct() o mecanismos que hayan
    evitado validación normal.
    """

    return OperationResult.model_validate(
        result.model_dump(
            mode="python"
        )
    )


def _revalidate_state(
    state: ProcedureRuntimeState,
) -> ProcedureRuntimeState:
    """
    Revalida también el runtime recibido.

    La correlación no confía únicamente en que el
    objeto Python tenga el tipo correcto.
    """

    return (
        ProcedureRuntimeState
        .model_validate(
            state.model_dump(
                mode="python"
            )
        )
    )


def validate_operation_result_against_runtime(
    result: OperationResult,
    state: ProcedureRuntimeState,
) -> None:
    """
    Correlaciona de forma determinista un
    OperationResult con el ProcedureRuntimeState
    actualmente autorizado para recibirlo.

    Responsabilidades:

    - revalidar ambos contratos;
    - exigir lifecycle WAITING_OPERATION;
    - rechazar replay/resultados ya registrados;
    - validar identidad operacional exacta;
    - validar operation_id determinista.

    NO:

    - modifica el runtime;
    - registra el resultado;
    - interpreta success/technical_success;
    - llama agentes;
    - llama tools/MCP;
    - decide la siguiente transición.
    """

    validated_result = (
        _revalidate_result(
            result
        )
    )

    validated_state = (
        _revalidate_state(
            state
        )
    )


    # --------------------------------------------------------
    # Replay / stale result
    # --------------------------------------------------------

    if (
        validated_state.operation_result
        is not None
    ):
        raise ValueError(
            "El runtime ya contiene un resultado "
            "operacional registrado. "
            "Se rechaza replay o resultado stale."
        )


    # --------------------------------------------------------
    # Lifecycle exacto esperado
    # --------------------------------------------------------

    if (
        validated_state.approval_id
        is None
    ):
        raise ValueError(
            "El runtime no contiene approval_id."
        )

    if (
        validated_state.approval_status
        != ApprovalStatus.APPROVED
    ):
        raise ValueError(
            "El runtime no contiene una "
            "aprobación vigente."
        )

    if (
        validated_state.step_status
        != StepStatus.RUNNING
    ):
        raise ValueError(
            "El paso activo no está en ejecución."
        )

    if (
        validated_state.workflow_status
        != WorkflowStatus.WAITING_OPERATION
    ):
        raise ValueError(
            "El workflow no está esperando "
            "un resultado operacional."
        )


    # --------------------------------------------------------
    # Identidad exacta result <-> runtime
    # --------------------------------------------------------

    comparisons = {
        "workflow_id": (
            validated_result.workflow_id,
            validated_state.workflow_id,
        ),

        "approval_id": (
            validated_result.approval_id,
            validated_state.approval_id,
        ),

        "alert_id": (
            validated_result.alert_id,
            validated_state.alert_id,
        ),

        "correlation_id": (
            validated_result.correlation_id,
            validated_state.correlation_id,
        ),

        "conversation_id": (
            validated_result.conversation_id,
            validated_state.conversation_id,
        ),

        "procedure_id": (
            validated_result.procedure_id,
            validated_state.procedure.id,
        ),

        "procedure_version": (
            validated_result.procedure_version,
            validated_state.procedure.version,
        ),

        "current_step": (
            validated_result.current_step,
            validated_state.current_step,
        ),

        "step_id": (
            validated_result.step_id,
            validated_state.step.id,
        ),

        "operation_domain": (
            validated_result.operation_domain,
            validated_state.step.operation_domain,
        ),

        "operation_kind": (
            validated_result.operation_kind,
            validated_state.step.operation_kind,
        ),

        "operation_action": (
            validated_result.operation_action,
            validated_state.step.operation_action,
        ),

        "capability_id": (
            validated_result.capability_id,
            validated_state.step.capability_id,
        ),

        "hitl_required": (
            validated_result.hitl_required,
            validated_state.step.hitl_required,
        ),

        "next_action": (
            validated_result.next_action,
            NextAction.EXECUTE_STEP,
        ),

        "target_resource": (
            validated_result.target_resource,
            validated_state.step.target_resource,
        ),

        "required_parameters": (
            list(
                validated_result
                .required_parameters
            ),

            list(
                validated_state
                .step
                .required_parameters
            ),
        ),

        "resolved_parameters": (
            _resolved_parameter_snapshot(
                validated_result
                .resolved_parameters
            ),

            _resolved_parameter_snapshot(
                validated_state
                .resolved_parameters
            ),
        ),
    }


    changed_fields = [
        field_name
        for field_name, values
        in comparisons.items()
        if values[0] != values[1]
    ]


    # --------------------------------------------------------
    # operation_id autoritativo
    # --------------------------------------------------------

    expected_operation_id = (
        create_operation_id(
            workflow_id=(
                validated_state.workflow_id
            ),

            approval_id=(
                validated_state.approval_id
            ),

            alert_id=(
                validated_state.alert_id
            ),

            procedure_id=(
                validated_state.procedure.id
            ),

            current_step=(
                validated_state.current_step
            ),

            step_id=(
                validated_state.step.id
            ),
        )
    )


    if (
        validated_result.operation_id
        != expected_operation_id
    ):
        changed_fields.append(
            "operation_id"
        )


    if changed_fields:
        raise ValueError(
            "OperationResult no corresponde "
            "exactamente al runtime activo. "
            "Campos distintos: "
            + ", ".join(
                changed_fields
            )
        )
