from __future__ import annotations

from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
)

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

from src.runtime.procedure.runtime import (
    ProcedureRuntime,
)

from src.runtime.procedure.workflow_state import (
    load_procedure_runtime_state,
    store_procedure_runtime_state,
)

from ..azure_operations_models import (
    VerifiedAzureOperationRequest,
)


def _resolved_parameter_snapshot(
    parameters,
) -> list[dict]:
    return [
        parameter.model_dump(
            mode="python"
        )
        for parameter
        in parameters
    ]


def _validate_request_against_runtime(
    request: VerifiedAzureOperationRequest,
    state: ProcedureRuntimeState,
) -> None:
    """
    Correlación determinista pre-dispatch.

    No interpreta semántica y no concede autoridad.
    Sólo comprueba que la operación ya verificada
    corresponde exactamente al runtime activo.
    """

    if not isinstance(
        request,
        VerifiedAzureOperationRequest,
    ):
        raise TypeError(
            "OperationStartExecutor requiere "
            "VerifiedAzureOperationRequest."
        )

    # Revalidación estructural fail-closed.
    VerifiedAzureOperationRequest.model_validate(
        request.model_dump(
            mode="python"
        )
    )

    if (
        state.approval_status
        != ApprovalStatus.APPROVED
    ):
        raise ValueError(
            "El runtime activo no contiene una "
            "aprobación humana vigente."
        )

    if (
        state.step_status
        != StepStatus.APPROVED
    ):
        raise ValueError(
            "El paso activo no está en estado approved."
        )

    if (
        state.workflow_status
        != WorkflowStatus.RUNNING
    ):
        raise ValueError(
            "El workflow no está preparado para "
            "iniciar una operación."
        )

    comparisons = {
        "workflow_id": (
            request.workflow_id,
            state.workflow_id,
        ),
        "approval_id": (
            request.approval_id,
            state.approval_id,
        ),
        "alert_id": (
            request.alert_id,
            state.alert_id,
        ),
        "correlation_id": (
            request.correlation_id,
            state.correlation_id,
        ),
        "conversation_id": (
            request.conversation_id,
            state.conversation_id,
        ),
        "procedure_id": (
            request.procedure_id,
            state.procedure.id,
        ),
        "procedure_version": (
            request.procedure_version,
            state.procedure.version,
        ),
        "current_step": (
            request.current_step,
            state.current_step,
        ),
        "step_id": (
            request.step_id,
            state.step.id,
        ),
        "operation_domain": (
            request.operation_domain,
            state.step.operation_domain,
        ),
        "operation_kind": (
            request.operation_kind,
            state.step.operation_kind,
        ),
        "next_action": (
            request.next_action,
            NextAction.EXECUTE_STEP,
        ),
        "target_resource": (
            request.target_resource,
            state.step.target_resource,
        ),
        "required_parameters": (
            list(
                request.required_parameters
            ),
            list(
                state.step.required_parameters
            ),
        ),
        "resolved_parameters": (
            _resolved_parameter_snapshot(
                request.resolved_parameters
            ),
            _resolved_parameter_snapshot(
                state.resolved_parameters
            ),
        ),
    }

    changed_fields = [
        field_name
        for field_name, values
        in comparisons.items()
        if values[0] != values[1]
    ]

    expected_operation_id = (
        create_operation_id(
            workflow_id=(
                state.workflow_id
            ),
            approval_id=(
                request.approval_id
            ),
            alert_id=(
                state.alert_id
            ),
            procedure_id=(
                state.procedure.id
            ),
            current_step=(
                state.current_step
            ),
            step_id=(
                state.step.id
            ),
        )
    )

    if (
        request.operation_id
        != expected_operation_id
    ):
        changed_fields.append(
            "operation_id"
        )

    if changed_fields:
        raise ValueError(
            "Verified operation request no corresponde "
            "exactamente al runtime activo. Campos "
            "distintos: "
            + ", ".join(
                changed_fields
            )
        )


class OperationStartExecutor(Executor):
    """
    Frontera determinista entre verificación
    pre-call y ejecución del backend.

    Sólo modifica lifecycle Python.
    No llama LLM, Foundry, MCP ni herramientas.
    """

    def __init__(self) -> None:
        super().__init__(
            id="operation_start"
        )

        self._runtime = (
            ProcedureRuntime()
        )

    @handler
    async def handle(
        self,
        request: VerifiedAzureOperationRequest,
        ctx: WorkflowContext[
            VerifiedAzureOperationRequest
        ],
    ) -> None:
        state = (
            load_procedure_runtime_state(
                ctx
            )
        )

        _validate_request_against_runtime(
            request,
            state,
        )

        state = (
            self._runtime
            .mark_operation_started(
                state
            )
        )

        store_procedure_runtime_state(
            ctx,
            state,
        )

        # El request verificado no se reconstruye
        # ni se modifica.
        await ctx.send_message(
            request
        )
