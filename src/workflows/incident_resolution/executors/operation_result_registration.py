from __future__ import annotations

from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
)

from src.runtime.procedure.models import (
    StepEvidence,
)

from src.runtime.procedure.runtime import (
    ProcedureRuntime,
)

from src.runtime.procedure.workflow_state import (
    load_procedure_runtime_state,
    store_procedure_runtime_state,
)

from ..operation_models import (
    OperationResult,
)

from ..operation_result_correlation import (
    validate_operation_result_against_runtime,
)

from ..procedure_validation_models import (
    ProcedureValidationRequest,
    ProcedureValidationStep,
)


class OperationResultRegistrationExecutor(
    Executor
):
    """
    Registra un OperationResult ya correlacionado
    contra el ProcedureRuntimeState autoritativo.

    Responsabilidades:

    - recuperar runtime autoritativo;
    - validar correlación exacta;
    - preservar el OperationResult completo;
    - mover lifecycle a WAITING_VALIDATION;
    - construir ProcedureValidationRequest.

    No interpreta éxito semántico.
    No llama LLM.
    No llama Foundry.
    No llama MCP.
    No decide la transición posterior.
    """

    def __init__(
        self,
    ) -> None:
        super().__init__(
            id="operation_result_registration"
        )

        self._runtime = (
            ProcedureRuntime()
        )

    @staticmethod
    def _build_step_evidence(
        result: OperationResult,
    ) -> StepEvidence:
        return StepEvidence(
            #
            # success se conserva como propiedad
            # del resultado operacional.
            #
            # register_operation_result() ya no
            # lo convierte en SUCCEEDED/FAILED.
            #
            success=(
                result.success
            ),

            result=(
                result.model_dump(
                    mode="json"
                )
            ),

            error=(
                result.error
            ),
        )

    @staticmethod
    def _build_validation_request(
        result: OperationResult,
        state,
    ) -> ProcedureValidationRequest:
        return ProcedureValidationRequest(
            operation_result=result,

            step=ProcedureValidationStep(
                procedure_id=(
                    state.procedure.id
                ),

                procedure_version=(
                    state.procedure.version
                ),

                current_step=(
                    state.current_step
                ),

                step_id=(
                    state.step.id
                ),

                description=(
                    state.step.description
                ),

                expected_result=(
                    state.step.expected_result
                ),

                verification=(
                    state.step.verification
                ),
            ),
        )

    @handler
    async def handle(
        self,
        result: OperationResult,
        ctx: WorkflowContext[
            ProcedureValidationRequest
        ],
    ) -> None:
        state = (
            load_procedure_runtime_state(
                ctx
            )
        )

        #
        # FASE 16.4.
        #
        # Esta llamada también revalida
        # estructuralmente OperationResult.
        #
        validate_operation_result_against_runtime(
            result,
            state,
        )

        evidence = (
            self._build_step_evidence(
                result
            )
        )

        state = (
            self._runtime
            .register_operation_result(
                state,
                evidence,
            )
        )

        validation_request = (
            self._build_validation_request(
                result,
                state,
            )
        )

        #
        # Persistimos primero el lifecycle.
        # Si la serialización falla, no sale
        # ningún mensaje downstream.
        #
        store_procedure_runtime_state(
            ctx,
            state,
        )

        await ctx.send_message(
            validation_request
        )

