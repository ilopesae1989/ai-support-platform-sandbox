from __future__ import annotations

import json

from dataclasses import (
    dataclass,
)

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

from src.runtime.procedure.models import (
    OperationAction,
    OperationKind,
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


@dataclass(
    frozen=True
)
class McpApprovalRequest:
    """
    Snapshot local de una solicitud de aprobación
    MCP propuesta por Foundry antes de ejecutar
    la tool.

    No representa autorización.

    approval_request_id:
        ID del item mcp_approval_request.

    response_id:
        ID de la Response superior que debe
        conservarse para previous_response_id.
    """

    approval_request_id: str
    response_id: str

    server_label: str
    tool_name: str

    arguments: dict[
        str,
        Any,
    ]


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
Acción operacional canónica: {
    (
        request.operation_action.value
        if request.operation_action
        is not None
        else "none"
    )
}
Acción del workflow: {request.next_action.value}
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
    def _mcp_approval_field(
        value,
        field_name: str,
    ):
        """
        Lee un campo desde objetos SDK o diccionarios.

        No intenta reconstruir campos ausentes.
        """

        if isinstance(
            value,
            dict,
        ):
            return value.get(
                field_name
            )

        return getattr(
            value,
            field_name,
            None,
        )

    @staticmethod
    def _parse_mcp_approval_arguments(
        arguments,
    ) -> dict[str, Any]:
        """
        Convierte exclusivamente argumentos MCP
        válidos a un objeto dict.

        A diferencia de la extracción de evidencia
        post-call, aquí NO existe fallback "raw":
        una solicitud que no pueda interpretarse
        exactamente se rechaza fail-closed.
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
            ) as exc:
                raise ValueError(
                    "mcp_approval_request contiene "
                    "arguments que no son JSON válido."
                ) from exc

            if not isinstance(
                parsed,
                dict,
            ):
                raise ValueError(
                    "mcp_approval_request.arguments "
                    "debe ser un objeto JSON."
                )

            return dict(
                parsed
            )

        raise ValueError(
            "mcp_approval_request.arguments tiene "
            "un tipo no autorizado."
        )

    @classmethod
    def _extract_mcp_approval_requests(
        cls,
        response,
    ) -> list[McpApprovalRequest]:
        """
        Extrae exclusivamente items
        type=mcp_approval_request.

        Preserva dos identidades distintas:

        - approval_request_id: item.id;
        - response_id: ID de la Response superior.

        response_id será posteriormente utilizado
        como previous_response_id.

        No aprueba nada.
        """

        raw_response = getattr(
            response,
            "raw_response",
            None,
        )

        raw_representation = getattr(
            response,
            "raw_representation",
            None,
        )

        nested_raw_representation = (
            getattr(
                raw_representation,
                "raw_representation",
                None,
            )
            if raw_representation is not None
            else None
        )

        # Agent Framework 1.13.0 observado LIVE:
        #
        # AgentResponse
        #   -> raw_representation: ChatResponse
        #       -> raw_representation: OpenAI Response
        #           -> output
        #
        # raw_response se conserva como shape legacy
        # utilizado por tests y adaptadores previos.
        #
        if raw_response is not None:
            response_source = raw_response

        elif nested_raw_representation is not None:
            response_source = (
                nested_raw_representation
            )

        elif raw_representation is not None:
            response_source = (
                raw_representation
            )

        else:
            response_source = response

        source_response_id = (
            cls._mcp_approval_field(
                response_source,
                "id",
            )
        )

        framework_response_id = (
            cls._mcp_approval_field(
                response,
                "response_id",
            )
        )

        if (
            source_response_id
            and framework_response_id
            and str(source_response_id)
            != str(framework_response_id)
        ):
            raise ValueError(
                "La identidad de la response MCP "
                "no coincide entre Agent Framework "
                "y la representación RAW."
            )

        response_id = (
            source_response_id
            or framework_response_id
        )

        output = (
            cls._mcp_approval_field(
                response_source,
                "output",
            )
            or cls._mcp_approval_field(
                response,
                "output",
            )
            or []
        )

        approvals: list[
            McpApprovalRequest
        ] = []

        for item in output:
            if (
                cls._mcp_approval_field(
                    item,
                    "type",
                )
                != "mcp_approval_request"
            ):
                continue

            approval_request_id = (
                cls._mcp_approval_field(
                    item,
                    "id",
                )
            )

            item_response_id = (
                cls._mcp_approval_field(
                    item,
                    "response_id",
                )
            )

            effective_response_id = (
                response_id
                or item_response_id
            )

            if (
                response_id
                and item_response_id
                and str(response_id)
                != str(item_response_id)
            ):
                raise ValueError(
                    "mcp_approval_request pertenece "
                    "a una response distinta."
                )

            server_label = (
                cls._mcp_approval_field(
                    item,
                    "server_label",
                )
            )

            tool_name = (
                cls._mcp_approval_field(
                    item,
                    "name",
                )
            )

            if not approval_request_id:
                raise ValueError(
                    "mcp_approval_request no tiene id."
                )

            if not effective_response_id:
                raise ValueError(
                    "mcp_approval_request no permite "
                    "determinar response_id."
                )

            if not server_label:
                raise ValueError(
                    "mcp_approval_request no tiene "
                    "server_label."
                )

            if not tool_name:
                raise ValueError(
                    "mcp_approval_request no tiene "
                    "nombre de tool."
                )

            arguments = (
                cls
                ._parse_mcp_approval_arguments(
                    cls._mcp_approval_field(
                        item,
                        "arguments",
                    )
                )
            )

            approvals.append(
                McpApprovalRequest(
                    approval_request_id=str(
                        approval_request_id
                    ),
                    response_id=str(
                        effective_response_id
                    ),
                    server_label=str(
                        server_label
                    ),
                    tool_name=str(
                        tool_name
                    ),
                    arguments=arguments,
                )
            )

        return approvals

    @classmethod
    def _extract_single_mcp_approval_request(
        cls,
        response,
    ) -> McpApprovalRequest:
        """
        WRITE gobernado admite exactamente una
        propuesta MCP.

        Cero o más de una se rechazan.
        """

        approvals = (
            cls._extract_mcp_approval_requests(
                response
            )
        )

        if len(approvals) != 1:
            raise ValueError(
                "La operación Azure WRITE requiere "
                "exactamente un mcp_approval_request. "
                f"Encontrados={len(approvals)}."
            )

        return approvals[0]

    @staticmethod
    def _validate_mcp_approval_request(
        request: VerifiedAzureOperationRequest,
        approval,
    ) -> None:
        """
        Verifica que la tool MCP propuesta por
        Foundry representa EXACTAMENTE la operación
        ya autorizada por la plataforma.

        Esta función NO concede approval.
        """

        request = (
            AzureOperationsExecutor
            ._revalidate_verified_request(
                request
            )
        )

        if (
            request.security_verified
            is not True
        ):
            raise ValueError(
                "MCP approval guard requiere una "
                "solicitud PreCall verificada."
            )

        if (
            request.verification_source
            != "pre_call_security_verifier"
        ):
            raise ValueError(
                "Origen de verificación inválido "
                "para MCP approval."
            )

        if (
            request.operation_kind
            != OperationKind.WRITE
        ):
            raise ValueError(
                "MCP approval automático sólo se "
                "evalúa para WRITE gobernado."
            )

        if (
            request.operation_action
            != OperationAction.VM_START
        ):
            raise ValueError(
                "La acción MCP propuesta no "
                "corresponde a VM_START."
            )

        if (
            request.capability_id
            != "azure.vm.start"
        ):
            raise ValueError(
                "Capability no autorizada para "
                "MCP VM Start."
            )

        if (
            request.hitl_required
            is not True
        ):
            raise ValueError(
                "VM Start debe proceder de una "
                "capability con HITL requerido."
            )

        if (
            getattr(
                approval,
                "server_label",
                None,
            )
            != "azure-mcp-operations-sbx"
        ):
            raise ValueError(
                "Servidor MCP distinto del "
                "servidor Azure gobernado."
            )

        if (
            getattr(
                approval,
                "tool_name",
                None,
            )
            != "compute_vm_power-state"
        ):
            raise ValueError(
                "Tool MCP distinta de la tool "
                "certificada para VM Start."
            )

        parameter_names = [
            parameter.name
            for parameter
            in request.resolved_parameters
        ]

        if (
            len(parameter_names)
            != len(set(parameter_names))
        ):
            raise ValueError(
                "Resolved parameters contiene "
                "nombres duplicados."
            )

        resolved = {
            parameter.name:
                parameter.value
            for parameter
            in request.resolved_parameters
        }

        expected_parameter_names = {
            "subscription_id",
            "resource_group",
            "vm_name",
        }

        if (
            set(resolved)
            != expected_parameter_names
        ):
            raise ValueError(
                "VM Start no contiene exactamente "
                "los parámetros gobernados."
            )

        expected_target = (
            "/subscriptions/"
            f"{resolved['subscription_id']}"
            "/resourceGroups/"
            f"{resolved['resource_group']}"
            "/providers/Microsoft.Compute/"
            "virtualMachines/"
            f"{resolved['vm_name']}"
        )

        if (
            request.target_resource is None
            or request.target_resource.casefold()
            != expected_target.casefold()
        ):
            raise ValueError(
                "Target resource no corresponde "
                "a los parámetros verificados."
            )

        expected_arguments = {
            "subscription":
                resolved[
                    "subscription_id"
                ],
            "resource-group":
                resolved[
                    "resource_group"
                ],
            "vm-name":
                resolved[
                    "vm_name"
                ],
            "power-action":
                "start",
        }

        actual_arguments = getattr(
            approval,
            "arguments",
            None,
        )

        if not isinstance(
            actual_arguments,
            dict,
        ):
            raise ValueError(
                "MCP approval arguments no es "
                "un objeto válido."
            )

        if (
            actual_arguments
            != expected_arguments
        ):
            raise ValueError(
                "Los argumentos MCP propuestos "
                "no coinciden exactamente con "
                "la operación autorizada."
            )

    @classmethod
    def _extract_correlated_native_mcp_approval_request(
        cls,
        response,
        approval: McpApprovalRequest,
    ):
        """
        Correlaciona la representación RAW de Foundry
        con el Content nativo de Agent Framework que
        posteriormente generará la approval response.

        Validar un objeto RAW y aprobar otro objeto
        distinto constituiría un bypass.

        Por ello deben coincidir exactamente:

        - número de solicitudes;
        - server_label;
        - tool;
        - arguments.
        """

        native_requests = list(
            getattr(
                response,
                "user_input_requests",
                None,
            )
            or []
        )

        if len(native_requests) != 1:
            raise ValueError(
                "Azure WRITE requiere exactamente "
                "un user_input_request MCP nativo. "
                f"Encontrados={len(native_requests)}."
            )

        native_request = (
            native_requests[0]
        )

        function_call = getattr(
            native_request,
            "function_call",
            None,
        )

        if function_call is None:
            raise ValueError(
                "El user_input_request no contiene "
                "function_call."
            )

        native_request_id = getattr(
            native_request,
            "id",
            None,
        )

        if not native_request_id:
            raise ValueError(
                "El user_input_request MCP nativo "
                "no contiene id."
            )

        function_call_id = getattr(
            function_call,
            "call_id",
            None,
        )

        if not function_call_id:
            raise ValueError(
                "El function_call MCP nativo no "
                "contiene call_id."
            )

        if (
            str(native_request_id)
            != approval.approval_request_id
        ):
            raise ValueError(
                "Mismatch entre RAW y Agent "
                "Framework: native id."
            )

        if (
            str(function_call_id)
            != approval.approval_request_id
        ):
            raise ValueError(
                "Mismatch entre RAW y Agent "
                "Framework: function_call call_id."
            )

        native_tool_name = getattr(
            function_call,
            "name",
            None,
        )

        if not native_tool_name:
            raise ValueError(
                "El function_call MCP nativo no "
                "contiene nombre de tool."
            )

        native_arguments = (
            cls._parse_mcp_approval_arguments(
                getattr(
                    function_call,
                    "arguments",
                    None,
                )
            )
        )

        function_call_additional_properties = (
            getattr(
                function_call,
                "additional_properties",
                None,
            )
        )

        if not isinstance(
            function_call_additional_properties,
            dict,
        ):
            raise ValueError(
                "El function_call MCP nativo no "
                "contiene additional_properties "
                "válidas."
            )

        native_server_label = (
            function_call_additional_properties.get(
                "server_label"
            )
        )

        if not native_server_label:
            raise ValueError(
                "El function_call MCP nativo no "
                "contiene server_label."
            )

        if (
            str(native_server_label)
            != approval.server_label
        ):
            raise ValueError(
                "Mismatch entre RAW y Agent "
                "Framework: server_label."
            )

        if (
            str(native_tool_name)
            != approval.tool_name
        ):
            raise ValueError(
                "Mismatch entre RAW y Agent "
                "Framework: tool."
            )

        if (
            native_arguments
            != approval.arguments
        ):
            raise ValueError(
                "Mismatch entre RAW y Agent "
                "Framework: arguments."
            )

        approval_factory = getattr(
            native_request,
            "to_function_approval_response",
            None,
        )

        #
        # Los fakes de integración delegan esta
        # comprobación en continue_azure_operations.
        #
        # En runtime real Content debe exponerla.
        #
        if (
            approval_factory is not None
            and not callable(
                approval_factory
            )
        ):
            raise ValueError(
                "La solicitud MCP nativa contiene "
                "un approval factory inválido."
            )

        return native_request

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

            operation_action=(
                request.operation_action
            ),

            capability_id=(
                request.capability_id
            ),

            hitl_required=(
                request.hitl_required
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
            #
            # READ conserva deliberadamente la ruta
            # histórica de una única invocación.
            #
            # WRITE gobernado utiliza una sesión
            # dedicada porque puede detenerse antes
            # de ejecutar MCP solicitando approval.
            #
            if (
                request.operation_kind
                == OperationKind.WRITE
            ):
                invocation = (
                    await self._agents
                    .begin_azure_operations(
                        prompt
                    )
                )

                response = getattr(
                    invocation,
                    "response",
                    None,
                )

                if response is None:
                    raise ValueError(
                        "Azure Operations WRITE no "
                        "devolvió respuesta inicial."
                    )

                #
                # RAW Foundry:
                # contiene approval_request_id,
                # response_id, server, tool y args.
                #
                approval = (
                    self
                    ._extract_single_mcp_approval_request(
                        response
                    )
                )

                #
                # AUTORIDAD:
                # compara la propuesta del modelo/MCP
                # contra VerifiedAzureOperationRequest.
                #
                self._validate_mcp_approval_request(
                    request,
                    approval,
                )

                #
                # Correlación anti-confusion:
                # el Content que se aprobará debe ser
                # exactamente la misma propuesta que
                # acabamos de validar en RAW.
                #
                native_approval_request = (
                    self
                    ._extract_correlated_native_mcp_approval_request(
                        response,
                        approval,
                    )
                )

                #
                # Esta aprobación es TÉCNICA.
                #
                # El HITL humano ya ocurrió antes de
                # VerifiedAzureOperationRequest.
                #
                # No vuelve a atravesar claim().
                #
                invocation = (
                    await self._agents
                    .continue_azure_operations(
                        invocation=invocation,
                        approval_request=(
                            native_approval_request
                        ),
                        approved=True,
                    )
                )

                response = getattr(
                    invocation,
                    "response",
                    None,
                )

                if response is None:
                    raise ValueError(
                        "Azure Operations WRITE no "
                        "devolvió respuesta después "
                        "del MCP approval."
                    )

            else:
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

                    operation_action=(
                        request.operation_action
                    ),

                    capability_id=(
                        request.capability_id
                    ),

                    hitl_required=(
                        request.hitl_required
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

                operation_action=(
                    request.operation_action
                ),

                capability_id=(
                    request.capability_id
                ),

                hitl_required=(
                    request.hitl_required
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
