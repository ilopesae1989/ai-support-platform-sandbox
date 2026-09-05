from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
    response_handler,
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
    build_procedure_repeat_input,
)

from ..models import (
    ProcedureExecutionInput,
)

from ..procedure_validation_models import (
    ProcedureValidationContext,
    ProcedureValidationRequest,
)

from ..wait_recheck import (
    WaitRecheckRequest,
    WaitRecheckSignal,
    build_wait_recheck_request,
    consume_wait_recheck_signal,
)

from ..wait_recheck_consumption_ledger import (
    InMemoryWaitRecheckConsumptionLedger,
    WaitRecheckConsumptionLedger,
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
        *,
        wait_recheck_consumption_ledger: (
            WaitRecheckConsumptionLedger | None
        ) = None,
    ) -> None:
        super().__init__(
            id="procedure_transition"
        )

        if (
            wait_recheck_consumption_ledger
            is None
        ):
            self._wait_recheck_consumption_ledger = (
                InMemoryWaitRecheckConsumptionLedger()
            )
        else:
            self._wait_recheck_consumption_ledger = (
                wait_recheck_consumption_ledger
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
        # CONTINUE avanza a N+1.
        # REPEAT reutiliza el cursor para un intento
        # operacional nuevo.
        #
        # Ambas decisiones proceden del Transition
        # Gate y se enrutan explícitamente.
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
        # REPEAT representa una operación nueva
        # del MISMO paso.
        #
        # El runtime ya invalidó completamente
        # la autoridad del intento anterior.
        #
        if (
            outcome.decision.next_action
            == NextAction.REPEAT
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

            repeat_input = (
                build_procedure_repeat_input(
                    outcome=outcome,
                    continuation=continuation,
                )
            )

            await ctx.send_message(
                repeat_input,
                target_id="procedure_execution",
            )

            return

        #
        # WAIT pausa el workflow esperando una
        # señal externa NO operacional.
        #
        if (
            outcome.decision.next_action
            == NextAction.WAIT
        ):
            request = (
                build_wait_recheck_request(
                    outcome.state
                )
            )

            await ctx.request_info(
                request_data=request,
                response_type=(
                    WaitRecheckSignal
                ),
                request_id=(
                    request.recheck_id
                ),
            )

            return

        #
        # RESOLVED, ESCALATE y BLOCKED
        # permanecen terminales.
        #
        await ctx.yield_output(
            outcome.state
        )

    @response_handler
    async def handle_wait_recheck_response(
        self,
        original_request: WaitRecheckRequest,
        response: WaitRecheckSignal,
        ctx: WorkflowContext[
            ProcedureValidationRequest,
            ProcedureRuntimeState,
        ],
    ) -> None:
        state = (
            load_procedure_runtime_state(
                ctx
            )
        )

        #
        # Primero se revalida y calcula el candidato
        # sobre una copia del runtime.
        #
        # consume_wait_recheck_signal() no persiste
        # ni modifica WorkflowContext.
        #
        (
            candidate_state,
            validation_request,
        ) = consume_wait_recheck_signal(
            state=state,
            original_request=(
                original_request
            ),
            signal=response,
        )

        #
        # Sólo una request/signal ya correlacionada
        # puede intentar reclamar autoridad.
        #
        # El claim ocurre ANTES de:
        # - persistir recheck_count;
        # - invalidar verification_result durable;
        # - enrutar a fresh-read.
        #
        self._wait_recheck_consumption_ledger.claim(
            original_request.recheck_id
        )

        store_procedure_runtime_state(
            ctx,
            candidate_state,
        )

        await ctx.send_message(
            validation_request,
            target_id=(
                "azure_vm_post_operation_observation"
            ),
        )
