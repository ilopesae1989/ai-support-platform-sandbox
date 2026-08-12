from __future__ import annotations

import json

from typing import (
    Any,
)

from agent_framework import (
    Content,
    Executor,
    WorkflowContext,
    handler,
)

from pydantic import (
    ValidationError,
)

from src.agents.foundry_agents import (
    FoundryAgents,
)

from ..azure_operations_models import (
    AzureOperationResult,
    VerifiedAzureOperationRequest,
)

from ..mcp_evidence import (
    McpCallEvidence,
)

from ..operation_dispatch_ledger import (
    InMemoryOperationDispatchLedger,
    OperationDispatchLedger,
)

from ..operation_evidence import (
    OperationEvidence,
)

from ..technical_evidence import (
    McpResultEvidence,
    ResponseErrorEvidence,
    ToolResultEvidence,
)

from ..tool_evidence import (
    ToolCallEvidence,
)


class AzureOperationsExecutor(Executor):
    def __init__(
        self,
        agents: FoundryAgents,
        operation_dispatch_ledger: (
            OperationDispatchLedger | None
        ) = None,
    ) -> None:
        super().__init__(
            id="azure_operations"
        )

        self._agents = agents

        self._operation_dispatch_ledger = (
            operation_dispatch_ledger
            or InMemoryOperationDispatchLedger()
        )

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

OperationId: {request.operation_id}
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

Operación exacta aprobada por el operador humano:
{request.description}

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

- Ejecuta exclusivamente la operación descrita en
  "Operación exacta aprobada por el operador humano".
- No sustituyas esa operación por otra operación
  aunque también sea de lectura.
- No amplíes, generalices ni reinterpretas la
  operación aprobada.
- No cambies el operation_id.
- No cambies el workflow.
- No cambies la aprobación.
- No cambies la alerta.
- No cambies el correlation_id.
- No cambies el conversation_id.
- No cambies el procedimiento.
- No cambies la versión.
- No cambies el paso.
- No cambies el dominio.
- No cambies el tipo de operación.
- No cambies la acción.
- No cambies el recurso objetivo.
- No cambies ningún parámetro aprobado.
- No amplíes el alcance solicitado.
- Utiliza exclusivamente los valores concretos aprobados.
- Si una herramienta no permite ejecutar exactamente
  la operación aprobada utilizando exactamente los
  parámetros autorizados, no ejecutes esa herramienta.
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

    @staticmethod
    def _resolved_parameters_copy(
        request: VerifiedAzureOperationRequest,
    ):
        return [
            parameter.model_copy(
                deep=True
            )
            for parameter
            in request.resolved_parameters
        ]

    @staticmethod
    def _normalize_tool_arguments(
        arguments: Any,
    ) -> dict[str, Any]:
        """
        Normaliza los argumentos de Content
        type=function_call.

        Agent Framework permite argumentos como
        diccionario o como JSON string.

        Si el valor no puede convertirse en un
        objeto JSON, se conserva sin pérdida bajo
        la clave raw.
        """

        if arguments is None:
            return {}

        if isinstance(
            arguments,
            dict,
        ):
            return dict(
                arguments
            )

        if isinstance(
            arguments,
            str,
        ):
            try:
                parsed = json.loads(
                    arguments
                )

            except (
                json.JSONDecodeError,
                TypeError,
            ):
                return {
                    "raw":
                        arguments
                }

            if isinstance(
                parsed,
                dict,
            ):
                return parsed

            return {
                "raw":
                    parsed
            }

        return {
            "raw":
                arguments
        }

    @staticmethod
    def _extract_tool_calls(
        response,
    ) -> list[ToolCallEvidence]:
        """
        Extrae únicamente Content con
        type=function_call.

        Agent Framework 2026 unifica los antiguos
        FunctionCallContent / FunctionResultContent
        en Content y exige discriminar por type.

        Los function_result NO se procesan en
        FASE 15.9.
        """

        tool_calls: list[
            ToolCallEvidence
        ] = []

        messages = (
            getattr(
                response,
                "messages",
                None,
            )
            or []
        )

        for message in messages:
            message_id = getattr(
                message,
                "message_id",
                None,
            )

            role = getattr(
                message,
                "role",
                None,
            )

            role_value = (
                getattr(
                    role,
                    "value",
                    role,
                )
                if role is not None
                else None
            )

            if role_value is not None:
                role_value = str(
                    role_value
                )

            contents = (
                getattr(
                    message,
                    "contents",
                    None,
                )
                or []
            )

            for content in contents:
                if not isinstance(
                    content,
                    Content,
                ):
                    continue

                if (
                    content.type
                    != "function_call"
                ):
                    continue

                tool_calls.append(
                    ToolCallEvidence(
                        tool_call_id=(
                            content.call_id
                        ),

                        tool_name=(
                            content.name
                        ),

                        arguments=(
                            AzureOperationsExecutor
                            ._normalize_tool_arguments(
                                content.arguments
                            )
                        ),

                        source_message_id=(
                            message_id
                        ),

                        source_message_role=(
                            role_value
                        ),
                    )
                )

        return tool_calls

    @staticmethod
    def _extract_mcp_calls(
        response,
    ) -> list[McpCallEvidence]:
        """
        Extrae exclusivamente Content con
        type=mcp_server_tool_call.

        Agent Framework representa estas llamadas
        como provider-hosted e informational_only.

        mcp_server_tool_result NO se procesa aquí.
        """

        mcp_calls: list[
            McpCallEvidence
        ] = []

        messages = (
            getattr(
                response,
                "messages",
                None,
            )
            or []
        )

        for message in messages:
            message_id = getattr(
                message,
                "message_id",
                None,
            )

            role = getattr(
                message,
                "role",
                None,
            )

            role_value = (
                getattr(
                    role,
                    "value",
                    role,
                )
                if role is not None
                else None
            )

            if role_value is not None:
                role_value = str(
                    role_value
                )

            contents = (
                getattr(
                    message,
                    "contents",
                    None,
                )
                or []
            )

            for content in contents:
                if not isinstance(
                    content,
                    Content,
                ):
                    continue

                if (
                    content.type
                    != "mcp_server_tool_call"
                ):
                    continue

                arguments = (
                    content.parse_arguments()
                )

                mcp_calls.append(
                    McpCallEvidence(
                        mcp_call_id=(
                            content.call_id
                        ),

                        server_name=(
                            content.server_name
                        ),

                        tool_name=(
                            content.tool_name
                        ),

                        arguments=(
                            dict(arguments)
                            if arguments
                            is not None
                            else {}
                        ),

                        source_message_id=(
                            message_id
                        ),

                        source_message_role=(
                            role_value
                        ),
                    )
                )

        return mcp_calls

    @staticmethod
    def _extract_tool_results(
        response,
    ) -> list[ToolResultEvidence]:
        results: list[
            ToolResultEvidence
        ] = []

        messages = (
            getattr(
                response,
                "messages",
                None,
            )
            or []
        )

        for message in messages:
            message_id = getattr(
                message,
                "message_id",
                None,
            )

            role = getattr(
                message,
                "role",
                None,
            )

            role_value = (
                getattr(
                    role,
                    "value",
                    role,
                )
                if role is not None
                else None
            )

            if role_value is not None:
                role_value = str(
                    role_value
                )

            for content in (
                getattr(
                    message,
                    "contents",
                    None,
                )
                or []
            ):
                if not isinstance(
                    content,
                    Content,
                ):
                    continue

                if (
                    content.type
                    != "function_result"
                ):
                    continue

                results.append(
                    ToolResultEvidence(
                        tool_call_id=(
                            content.call_id
                        ),

                        result_text=(
                            content.result
                        ),

                        exception=(
                            content.exception
                        ),

                        source_message_id=(
                            message_id
                        ),

                        source_message_role=(
                            role_value
                        ),
                    )
                )

        return results

    @staticmethod
    def _extract_mcp_results(
        response,
    ) -> list[McpResultEvidence]:
        results: list[
            McpResultEvidence
        ] = []

        messages = (
            getattr(
                response,
                "messages",
                None,
            )
            or []
        )

        for message in messages:
            message_id = getattr(
                message,
                "message_id",
                None,
            )

            role = getattr(
                message,
                "role",
                None,
            )

            role_value = (
                getattr(
                    role,
                    "value",
                    role,
                )
                if role is not None
                else None
            )

            if role_value is not None:
                role_value = str(
                    role_value
                )

            for content in (
                getattr(
                    message,
                    "contents",
                    None,
                )
                or []
            ):
                if not isinstance(
                    content,
                    Content,
                ):
                    continue

                if (
                    content.type
                    != "mcp_server_tool_result"
                ):
                    continue

                results.append(
                    McpResultEvidence(
                        mcp_call_id=(
                            content.call_id
                        ),

                        output=(
                            content.output
                        ),

                        source_message_id=(
                            message_id
                        ),

                        source_message_role=(
                            role_value
                        ),
                    )
                )

        return results

    @staticmethod
    def _extract_response_errors(
        response,
    ) -> list[ResponseErrorEvidence]:
        errors: list[
            ResponseErrorEvidence
        ] = []

        messages = (
            getattr(
                response,
                "messages",
                None,
            )
            or []
        )

        for message in messages:
            message_id = getattr(
                message,
                "message_id",
                None,
            )

            role = getattr(
                message,
                "role",
                None,
            )

            role_value = (
                getattr(
                    role,
                    "value",
                    role,
                )
                if role is not None
                else None
            )

            if role_value is not None:
                role_value = str(
                    role_value
                )

            for content in (
                getattr(
                    message,
                    "contents",
                    None,
                )
                or []
            ):
                if not isinstance(
                    content,
                    Content,
                ):
                    continue

                if (
                    content.type
                    != "error"
                ):
                    continue

                errors.append(
                    ResponseErrorEvidence(
                        message=(
                            content.message
                        ),

                        error_code=(
                            content.error_code
                        ),

                        error_details=(
                            content.error_details
                        ),

                        source_message_id=(
                            message_id
                        ),

                        source_message_role=(
                            role_value
                        ),
                    )
                )

        return errors

    @classmethod
    def _build_operation_evidence(
        cls,
        request: VerifiedAzureOperationRequest,
        response,
    ) -> OperationEvidence | None:
        tool_calls = (
            cls._extract_tool_calls(
                response
            )
        )

        mcp_calls = (
            cls._extract_mcp_calls(
                response
            )
        )

        tool_results = (
            cls._extract_tool_results(
                response
            )
        )

        mcp_results = (
            cls._extract_mcp_results(
                response
            )
        )

        response_errors = (
            cls._extract_response_errors(
                response
            )
        )

        if (
            not tool_calls
            and not mcp_calls
            and not tool_results
            and not mcp_results
            and not response_errors
        ):
            return None

        return OperationEvidence(
            operation_id=(
                request.operation_id
            ),

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

            conversation_id=(
                request.conversation_id
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

            operation_domain=(
                request.operation_domain
            ),

            operation_kind=(
                request.operation_kind
            ),

            next_action=(
                request.next_action
            ),

            target_resource=(
                request.target_resource
            ),

            required_parameters=list(
                request.required_parameters
            ),

            resolved_parameters=(
                cls._resolved_parameters_copy(
                    request
                )
            ),

            tool_calls=tool_calls,
            mcp_calls=mcp_calls,

            tool_results=(
                tool_results
            ),

            mcp_results=(
                mcp_results
            ),

            response_errors=(
                response_errors
            ),
        )

    @staticmethod
    def _revalidate_verified_request(
        request: VerifiedAzureOperationRequest,
    ) -> VerifiedAzureOperationRequest:
        """
        Última comprobación estructural antes
        de invocar Foundry.

        No sustituye PreCallSecurityVerifier.

        Su finalidad es impedir que objetos
        construidos sin validación normal
        (por ejemplo model_construct) lleguen
        silenciosamente al backend.
        """

        if not isinstance(
            request,
            VerifiedAzureOperationRequest,
        ):
            raise ValueError(
                "Azure Operations requiere "
                "VerifiedAzureOperationRequest."
            )

        try:
            return (
                VerifiedAzureOperationRequest
                .model_validate(
                    request
                )
            )

        except ValidationError as exc:
            raise ValueError(
                "Azure Operations recibió una "
                "solicitud verificada cuya "
                "integridad estructural no es "
                "válida."
            ) from exc

    @staticmethod
    async def _emit_result(
        ctx,
        result: AzureOperationResult,
    ) -> None:
        """
        Emite exactamente la misma instancia de
        AzureOperationResult hacia:

        - downstream mediante send_message();
        - output mediante yield_output().

        No reconstruye el resultado.
        No modifica identidad ni evidencia.
        """

        await ctx.send_message(
            result
        )

        await ctx.yield_output(
            result
        )

    @handler
    async def handle(
        self,
        request: VerifiedAzureOperationRequest,
        ctx: WorkflowContext[
            AzureOperationResult,
            AzureOperationResult,
        ],
    ) -> None:
        request = (
            self._revalidate_verified_request(
                request
            )
        )

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

        #
        # --------------------------------------------------
        # Monotonic dispatch gate
        # --------------------------------------------------
        #
        # Esta autoridad NO pertenece al checkpoint
        # del workflow.
        #
        # Una restauración histórica puede recuperar
        # nuevamente:
        #
        #     VerifiedAzureOperationRequest
        #
        # pero no puede recuperar el derecho a
        # despachar otra vez el mismo operation_id.
        #
        # El claim ocurre DESPUÉS de todas las
        # verificaciones locales y ANTES de cualquier
        # llamada a Foundry/MCP.
        #
        # Deliberadamente está fuera del try/except
        # destinado a fallos de Foundry:
        #
        # un replay no es un AzureOperationResult
        # fallido; es una violación de la frontera de
        # dispatch y debe detener el workflow.
        #
        self._operation_dispatch_ledger.claim(
            request.operation_id
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
            await self._emit_result(
                ctx,
                AzureOperationResult(
                    operation_id=(
                        request.operation_id
                    ),

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

                    conversation_id=(
                        request.conversation_id
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

                    operation_domain=(
                        request.operation_domain
                    ),

                    operation_kind=(
                        request.operation_kind
                    ),

                    next_action=(
                        request.next_action
                    ),

                    target_resource=(
                        request.target_resource
                    ),

                    required_parameters=list(
                        request.required_parameters
                    ),

                    resolved_parameters=(
                        self._resolved_parameters_copy(
                            request
                        )
                    ),

                    success=False,

                    response_text=None,

                    error=(
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),

                    technical_success=False,

                    evidence=None,
                )
            )

            return

        evidence = (
            self._build_operation_evidence(
                request,
                response,
            )
        )

        technical_success = (
            evidence.derive_technical_success()
            if evidence is not None
            else None
        )

        await self._emit_result(
            ctx,
            AzureOperationResult(
                operation_id=(
                    request.operation_id
                ),

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

                conversation_id=(
                    request.conversation_id
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

                operation_domain=(
                    request.operation_domain
                ),

                operation_kind=(
                    request.operation_kind
                ),

                next_action=(
                    request.next_action
                ),

                target_resource=(
                    request.target_resource
                ),

                required_parameters=list(
                    request.required_parameters
                ),

                resolved_parameters=(
                    self._resolved_parameters_copy(
                        request
                    )
                ),

                success=True,

                response_text=(
                    self._extract_response_text(
                        response
                    )
                ),

                error=None,

                technical_success=(
                    technical_success
                ),

                evidence=evidence,
            )
        )
