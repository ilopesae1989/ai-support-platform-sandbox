from __future__ import annotations

from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
)

from src.agents.foundry_agents import (
    FoundryAgents,
)

from ..azure_operations_models import (
    AzureOperationResult,
    VerifiedAzureOperationRequest,
)


class AzureOperationsExecutor(Executor):
    def __init__(
        self,
        agents: FoundryAgents,
    ) -> None:
        super().__init__(
            id="azure_operations"
        )

        self._agents = agents

    @staticmethod
    def _build_prompt(
        request: VerifiedAzureOperationRequest,
    ) -> str:
        required_parameters = (
            "\n".join(
                f"- {parameter_name}"
                for parameter_name
                in request.required_parameters
            )
            if request.required_parameters
            else "- Ninguno"
        )

        resolved_parameters = (
            "\n".join(
                (
                    f"- {parameter.name} = "
                    f"{parameter.value}"
                )
                for parameter
                in request.resolved_parameters
            )
            if request.resolved_parameters
            else "- Ninguno"
        )

        return f"""
Procesa exclusivamente la siguiente operación Azure
previamente aprobada y verificada por el workflow.

WorkflowId: {request.workflow_id}
ApprovalId: {request.approval_id}
AlertId: {request.alert_id}
CorrelationId: {request.correlation_id or "none"}
ConversationId: {request.conversation_id or "none"}

Procedimiento:
ID: {request.procedure_id}
Versión: {request.procedure_version or "unknown"}

Paso:
Número: {request.current_step}
ID: {request.step_id}

Operación:
Dominio: {request.operation_domain}
Tipo: {request.operation_kind.value}
Acción: {request.next_action.value}
Recurso objetivo: {request.target_resource or "unknown"}

Parámetros requeridos:
{required_parameters}

Parámetros aprobados y resueltos:
{resolved_parameters}

Restricciones obligatorias:

- No cambies el workflow.
- No cambies la aprobación.
- No cambies la alerta.
- No cambies el correlation_id.
- No cambies el procedimiento.
- No cambies la versión.
- No cambies el paso.
- No cambies el dominio.
- No cambies el tipo de operación.
- No cambies el recurso objetivo.
- No cambies ningún parámetro aprobado.
- No amplíes el alcance solicitado.
- Utiliza exclusivamente los valores concretos aprobados.
- Si una herramienta requiere argumentos distintos,
  no ejecutes esa herramienta.
""".strip()

    @staticmethod
    def _extract_response_text(
        response,
    ) -> str | None:
        text = getattr(
            response,
            "text",
            None,
        )

        if text:
            return str(
                text
            ).strip()

        return None

    @handler
    async def handle(
        self,
        request: VerifiedAzureOperationRequest,
        ctx: WorkflowContext[
            None,
            AzureOperationResult,
        ],
    ) -> None:
        if (
            request.security_verified
            is not True
        ):
            raise ValueError(
                "Azure Operations recibió una "
                "solicitud no verificada."
            )

        if (
            request.verification_source
            != "pre_call_security_verifier"
        ):
            raise ValueError(
                "Azure Operations recibió una "
                "solicitud con origen de "
                "verificación inválido."
            )

        prompt = (
            self._build_prompt(
                request
            )
        )

        try:
            response = (
                await self._agents
                .run_azure_operations(
                    prompt
                )
            )

        except Exception as exc:
            await ctx.yield_output(
                AzureOperationResult(
                    workflow_id=(
                        request.workflow_id
                    ),

                    approval_id=(
                        request.approval_id
                    ),

                    alert_id=(
                        request.alert_id
                    ),

                    correlation_id=(
                        request.correlation_id
                    ),

                    procedure_id=(
                        request.procedure_id
                    ),

                    procedure_version=(
                        request.procedure_version
                    ),

                    current_step=(
                        request.current_step
                    ),

                    step_id=(
                        request.step_id
                    ),

                    operation_kind=(
                        request.operation_kind
                    ),

                    target_resource=(
                        request.target_resource
                    ),

                    success=False,

                    response_text=None,

                    error=(
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                )
            )

            return

        await ctx.yield_output(
            AzureOperationResult(
                workflow_id=(
                    request.workflow_id
                ),

                approval_id=(
                    request.approval_id
                ),

                alert_id=(
                    request.alert_id
                ),

                correlation_id=(
                    request.correlation_id
                ),

                procedure_id=(
                    request.procedure_id
                ),

                procedure_version=(
                    request.procedure_version
                ),

                current_step=(
                    request.current_step
                ),

                step_id=(
                    request.step_id
                ),

                operation_kind=(
                    request.operation_kind
                ),

                target_resource=(
                    request.target_resource
                ),

                success=True,

                response_text=(
                    self._extract_response_text(
                        response
                    )
                ),

                error=None,
            )
        )