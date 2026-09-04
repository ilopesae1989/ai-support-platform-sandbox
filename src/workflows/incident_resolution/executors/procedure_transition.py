from __future__ import annotations

from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
)

from src.runtime.procedure.models import (
    NextAction,
    ProcedureRuntimeState,
)

from src.runtime.procedure.workflow_state import (
    load_procedure_runtime_state,
    store_procedure_runtime_state,
)

from ..continuation_context import (
    load_procedure_continuation_context,
)

from ..procedure_transition_gate import (
    apply_procedure_validation_transition_with_outcome,
)

from ..continuation_request_builder import (
    build_procedure_continuation_input,
)

from ..models import (
    ProcedureExecutionInput,
)

from ..procedure_validation_models import (
    ProcedureValidationContext,
)


class ProcedureTransitionExecutor(
    Executor
):
    """
    Adapter determinista entre Procedure Validation
    y el ProcedureRuntimeState autoritativo.

    Responsabilidades:

    - cargar el estado autoritativo;
    - delegar toda la política al Transition Gate;
    - persistir únicamente una transición válida;
    - producir el snapshot resultante.

    No interpreta semántica.
    No llama agentes.
    No llama Foundry.
    No llama MCP.
    No ejecuta herramientas.
    No duplica reglas del Transition Gate.
    """

    def __init__(
        self,
    ) -> None:
        super().__init__(
            id="procedure_transition"
        )

    @handler
    async def handle(
        self,
        context: ProcedureValidationContext,
        ctx: WorkflowContext[
            ProcedureExecutionInput,
            ProcedureRuntimeState,
        ],
    ) -> None:
        #
        # El estado almacenado en WorkflowContext
        # es la única fuente autoritativa.
        #
        state = (
            load_procedure_runtime_state(
                ctx
            )
        )

        #
        # Toda validación de identidad, replay,
        # operación, paso y transición reside
        # exclusivamente en el gate de FASE 16.7.
        #
        outcome = (
            apply_procedure_validation_transition_with_outcome(
                state=state,
                context=context,
            )
        )

        #
        # Fail-closed:
        #
        # la transición determinista se persiste
        # antes de cualquier routing posterior.
        #
        store_procedure_runtime_state(
            ctx,
            outcome.state,
        )

        #
        # CONTINUE es la única decisión que puede
        # producir un nuevo ProcedureExecutionInput.
        #
        # La decisión procede del Transition Gate.
        # No se infiere de status ni del cursor.
        #
        if (
            outcome.decision.next_action
            == NextAction.CONTINUE
        ):
            continuation = (
                load_procedure_continuation_context(
                    ctx
                )
            )

            if continuation is None:
                raise RuntimeError(
                    "ProcedureContinuationContext "
                    "durable no disponible."
                )

            next_input = (
                build_procedure_continuation_input(
                    outcome=outcome,
                    continuation=continuation,
                )
            )

            await ctx.send_message(
                next_input,
                target_id="procedure_execution",
            )

            return

        #
        # Todas las decisiones distintas de
        # CONTINUE siguen siendo terminales para
        # este ciclo del workflow.
        #
        await ctx.yield_output(
            outcome.state
        )
