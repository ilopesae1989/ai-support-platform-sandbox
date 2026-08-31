from __future__ import annotations

import json

from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
)

from src.agents.foundry_agents import (
    FoundryAgents,
)

from ..procedure_validation_models import (
    ProcedureValidationContext,
    ProcedureValidationRequest,
)


class ProcedureValidationExecutor(
    Executor
):
    """
    Interpretación cognitiva post-operación.

    No lee ni modifica workflow state.
    No ejecuta operaciones.
    No aplica transiciones.
    """

    def __init__(
        self,
        agents: FoundryAgents,
    ) -> None:
        super().__init__(
            id="procedure_validation"
        )

        self._agents = agents

    @staticmethod
    def _revalidate_request(
        request: ProcedureValidationRequest,
    ) -> ProcedureValidationRequest:
        return (
            ProcedureValidationRequest
            .model_validate(
                request.model_dump(
                    mode="python"
                )
            )
        )

    @staticmethod
    def _build_prompt(
        request: ProcedureValidationRequest,
    ) -> str:
        result = (
            request.operation_result
        )

        payload = {
            "mode": "validate_result",

            "trusted_identity": {
                "operation_id": (
                    result.operation_id
                ),
                "workflow_id": (
                    result.workflow_id
                ),
                "approval_id": (
                    result.approval_id
                ),
                "alert_id": (
                    result.alert_id
                ),
                "correlation_id": (
                    result.correlation_id
                ),
                "conversation_id": (
                    result.conversation_id
                ),
                "procedure_id": (
                    result.procedure_id
                ),
                "procedure_version": (
                    result.procedure_version
                ),
                "current_step": (
                    result.current_step
                ),
                "step_id": (
                    result.step_id
                ),
            },

            "step": (
                request.step.model_dump(
                    mode="json"
                )
            ),

            "operation_result": (
                result.model_dump(
                    mode="json"
                )
            ),

            "post_operation_observation": (
                request
                .post_operation_observation
                .model_dump(
                    mode="json"
                )
                if (
                    request
                    .post_operation_observation
                    is not None
                )
                else None
            ),

            "constraints": [
                "Interpret only according to the procedure.",
                "Foundry IQ knowledge retrieval is allowed.",
                "Treat post_operation_observation as trusted read-only evidence when present.",
                "A completed WRITE does not by itself prove current resource state.",
                "Do not execute operational actions.",
                "Do not modify workflow state.",
                "Do not authorize any operation.",
                "Do not return execute_step.",
            ],
        }

        return json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )

    @handler
    async def handle(
        self,
        request: ProcedureValidationRequest,
        ctx: WorkflowContext[
            ProcedureValidationContext
        ],
    ) -> None:
        trusted_request = (
            self._revalidate_request(
                request
            )
        )

        prompt = (
            self._build_prompt(
                trusted_request
            )
        )

        result = (
            await self._agents
            .run_procedure_validation(
                prompt
            )
        )

        context = (
            ProcedureValidationContext(
                request=trusted_request,
                result=result,
            )
        )

        await ctx.send_message(
            context
        )
