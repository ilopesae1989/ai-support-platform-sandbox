from __future__ import annotations

from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
)

from src.runtime.procedure.models import (
    ProcedureRuntimeState,
)

from src.runtime.procedure.workflow_state import (
    load_procedure_runtime_state,
    store_procedure_runtime_state,
)

from ..procedure_transition_gate import (
    apply_procedure_validation_transition,
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
            None,
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
        transitioned_state = (
            apply_procedure_validation_transition(
                state=state,
                context=context,
            )
        )

        #
        # Fail-closed:
        #
        # sólo persistimos después de que el gate
        # haya finalizado correctamente.
        #
        store_procedure_runtime_state(
            ctx,
            transitioned_state,
        )

        #
        # Salida terminal temporal de FASE 16.
        #
        # En FASE 17 podrá sustituirse por routing
        # determinista hacia el siguiente ciclo.
        #
        await ctx.yield_output(
            transitioned_state
        )
