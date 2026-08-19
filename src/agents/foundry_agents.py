import json
import logging
import os

from dataclasses import (
    dataclass,
)

from typing import Mapping

from agent_framework import (
    ChatOptions,
    Message,
)

from agent_framework.foundry import FoundryAgent
from azure.identity import AzureCliCredential
from pydantic import ValidationError

from .audit import AgentInvocationMetadata
from .catalog import (
    AgentKey,
    FoundryAgentDefinition,
    build_agent_catalog,
    get_agent_definition,
)
from .contracts import (
    AlertTriageResult,
    ClassificationResult,
    KnowledgeResult,
    ProcedureExecutionResult,
    ProcedureValidationResult,
)


logger = logging.getLogger(__name__)


@dataclass(
    frozen=True
)
class AzureOperationsInvocation:
    """
    Contexto efímero de una única ejecución
    Azure Operations que puede requerir una
    continuación MCP.

    Mantiene:

    - la misma instancia de FoundryAgent;
    - la misma AgentSession;
    - la respuesta más reciente.

    No representa autorización.

    No es un checkpoint durable.

    La autorización operacional continúa
    perteneciendo al workflow y a
    VerifiedAzureOperationRequest.
    """

    agent: object
    session: object
    response: object

    owner_token: object


class FoundryAgents:
    """
    Adaptadores hacia Prompt Agents administrados
    en Microsoft Foundry.

    Responsabilidades:
    - resolver el agente y su versión desde el
      catálogo central;
    - crear FoundryAgent con la definición versionada;
    - invocar los Prompt Agents autorizados;
    - extraer JSON textual cuando existe contrato
      estructurado;
    - validar respuestas mediante contratos Pydantic;
    - registrar metadatos mínimos de auditoría.

    No define instrucciones.
    No añade herramientas.
    No añade MCP.
    No modifica Knowledge.
    No decide routing.
    No gestiona HITL del workflow.
    No mantiene el estado durable del workflow.

    IMPORTANTE:
    agent-azure-operations-sbx puede tener tools/MCP
    configurados server-side en Microsoft Foundry.

    Por ello su invocación puede producir efectos
    externos y se mantiene separada de los agentes
    puramente cognitivos.
    """

    def __init__(
        self,
        project_endpoint: str | None = None,
        catalog: Mapping[
            AgentKey,
            FoundryAgentDefinition,
        ] | None = None,
    ) -> None:
        self._project_endpoint = (
            project_endpoint
            or os.environ.get(
                "FOUNDRY_PROJECT_ENDPOINT"
            )
        )

        if not self._project_endpoint:
            raise ValueError(
                "FOUNDRY_PROJECT_ENDPOINT "
                "no está configurado."
            )

        #
        # Desarrollo local:
        # Azure CLI del operador.
        #
        # En producción este componente se sustituirá
        # por la identidad administrada correspondiente.
        #
        self._credential = AzureCliCredential()

        #
        # Contextos Azure Operations iniciados por esta
        # instancia sólo pueden continuarse mediante
        # esta misma instancia.
        #
        # No es una credencial ni se serializa.
        #
        self._azure_operations_owner_token = object()

        #
        # El catálogo efectivo se construye una sola vez
        # para esta instancia.
        #
        # Todas las invocaciones realizadas por la
        # instancia utilizan por tanto una configuración
        # consistente de versiones.
        #
        self._catalog = (
            catalog
            if catalog is not None
            else build_agent_catalog()
        )

    def get_definition(
        self,
        key: AgentKey,
    ) -> FoundryAgentDefinition:
        """
        Obtiene la definición efectiva de un agente.

        El nombre y la versión proceden exclusivamente
        del catálogo central.
        """

        return get_agent_definition(
            key,
            self._catalog,
        )

    def _create_agent(
        self,
        definition: FoundryAgentDefinition,
    ) -> FoundryAgent:
        """
        Crea un FoundryAgent para una definición
        versionada del catálogo.

        Azure Operations recibe además una política
        de ejecución que limita una aprobación a una
        única tool call del backend.

        La política se configura mediante
        default_options porque el runtime instalado
        no acepta extra_body como argumento directo
        de Agent.run().
        """

        default_options = None

        if (
            definition.key
            == AgentKey.AZURE_OPERATIONS
        ):
            default_options = {
                "extra_body": {
                    "max_tool_calls": 1,
                    "parallel_tool_calls": False,
                }
            }

        return FoundryAgent(
            project_endpoint=(
                self._project_endpoint
            ),

            agent_name=(
                definition.name
            ),

            agent_version=(
                definition.version
            ),

            credential=(
                self._credential
            ),

            default_options=(
                default_options
            ),

            timeout=120.0,
        )

    @staticmethod
    def _register_invocation(
        definition: FoundryAgentDefinition,
    ) -> AgentInvocationMetadata:
        """
        Genera y registra evidencia mínima de la
        definición de agente utilizada.

        No registra:
        - prompts;
        - secretos;
        - credenciales;
        - chain-of-thought.
        """

        metadata = (
            AgentInvocationMetadata.from_definition(
                definition
            )
        )

        logger.info(
            "foundry_agent_invocation "
            "agent_key=%s "
            "agent_name=%s "
            "agent_version=%s "
            "invoked_at_utc=%s",
            metadata.agent_key.value,
            metadata.agent_name,
            metadata.agent_version,
            metadata.invoked_at_utc,
        )

        return metadata

    @staticmethod
    def _extract_json_text(
        response,
    ) -> str:
        """
        Extrae exclusivamente el contenido textual
        devuelto por el Prompt Agent.

        No interpreta semánticamente la respuesta.
        """

        text = getattr(
            response,
            "text",
            None,
        )

        if text:
            return text.strip()

        messages = getattr(
            response,
            "messages",
            None,
        )

        if messages:
            for message in reversed(messages):
                message_text = getattr(
                    message,
                    "text",
                    None,
                )

                if message_text:
                    return message_text.strip()

        raise RuntimeError(
            "El Prompt Agent no devolvió "
            "contenido textual."
        )

    @staticmethod
    def _parse_json(
        text: str,
    ) -> dict:
        """
        Convierte exclusivamente JSON válido.

        No intenta reparar respuestas.
        No elimina Markdown.
        No completa campos.
        """

        try:
            value = json.loads(
                text
            )

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "El Prompt Agent no devolvió "
                "JSON válido."
            ) from exc

        if not isinstance(
            value,
            dict,
        ):
            raise RuntimeError(
                "La respuesta del Prompt Agent "
                "debe ser un objeto JSON."
            )

        return value

    async def run_classification(
        self,
        message: str,
    ) -> ClassificationResult:
        """
        Invoca la capacidad lógica de clasificación
        utilizando exclusivamente la definición
        efectiva del catálogo.

        No decide routing.
        No gestiona aprobaciones.
        No ejecuta operaciones.
        """

        definition = self.get_definition(
            AgentKey.CLASSIFICATION
        )

        self._register_invocation(
            definition
        )

        agent = self._create_agent(
            definition
        )

        response = await agent.run(
            message
        )

        text = self._extract_json_text(
            response
        )

        payload = self._parse_json(
            text
        )

        try:
            return (
                ClassificationResult.model_validate(
                    payload
                )
            )

        except ValidationError as exc:
            raise RuntimeError(
                f"{definition.name} "
                f"v{definition.version} "
                "devolvió un JSON que no cumple "
                "el contrato ClassificationResult."
            ) from exc

    async def run_knowledge(
        self,
        message: str,
    ) -> KnowledgeResult:
        """
        Invoca la capacidad lógica de conocimiento
        utilizando exclusivamente la definición
        efectiva del catálogo.

        No interpreta aplicabilidad.
        No decide routing.
        No ejecuta procedimientos.
        """

        definition = self.get_definition(
            AgentKey.KNOWLEDGE
        )

        self._register_invocation(
            definition
        )

        agent = self._create_agent(
            definition
        )

        response = await agent.run(
            message
        )

        text = self._extract_json_text(
            response
        )

        payload = self._parse_json(
            text
        )

        try:
            return (
                KnowledgeResult.model_validate(
                    payload
                )
            )

        except ValidationError as exc:
            raise RuntimeError(
                f"{definition.name} "
                f"v{definition.version} "
                "devolvió un JSON que no cumple "
                "el contrato KnowledgeResult."
            ) from exc

    async def run_alert_triage(
        self,
        message: str,
    ) -> AlertTriageResult:
        """
        Invoca la capacidad de triage de alertas
        utilizando exclusivamente la definición
        efectiva del catálogo.
        """

        definition = self.get_definition(
            AgentKey.ALERT_TRIAGE
        )

        self._register_invocation(
            definition
        )

        agent = self._create_agent(
            definition
        )

        response = await agent.run(
            message
        )

        text = self._extract_json_text(
            response
        )

        payload = self._parse_json(
            text
        )

        try:
            return (
                AlertTriageResult.model_validate(
                    payload
                )
            )

        except ValidationError as exc:
            raise RuntimeError(
                f"{definition.name} "
                f"v{definition.version} "
                "devolvió un JSON que no cumple "
                "el contrato AlertTriageResult."
            ) from exc

    async def run_procedure_execution(
        self,
        message: str,
    ) -> ProcedureExecutionResult:
        """
        Invoca la capacidad de ejecución de
        procedimientos utilizando exclusivamente
        la definición efectiva del catálogo.
        """

        definition = self.get_definition(
            AgentKey.PROCEDURE_EXECUTION
        )

        self._register_invocation(
            definition
        )

        agent = self._create_agent(
            definition
        )

        response = await agent.run(
            message
        )

        text = self._extract_json_text(
            response
        )

        payload = self._parse_json(
            text
        )

        try:
            return (
                ProcedureExecutionResult.model_validate(
                    payload
                )
            )

        except ValidationError as exc:
            raise RuntimeError(
                f"{definition.name} "
                f"v{definition.version} "
                "devolvió un JSON que no cumple "
                "el contrato ProcedureExecutionResult."
            ) from exc

    async def run_procedure_validation(
        self,
        message: str,
    ) -> ProcedureValidationResult:
        """
        Invoca la interpretación post-operación
        del Procedure Agent.

        Utiliza PROCEDURE_EXECUTION, pero valida
        exclusivamente ProcedureValidationResult.

        No repara respuestas ni convierte
        silenciosamente contratos antiguos.
        """

        definition = self.get_definition(
            AgentKey.PROCEDURE_EXECUTION
        )

        self._register_invocation(
            definition
        )

        agent = self._create_agent(
            definition
        )

        response = await agent.run(
            message
        )

        response_text = (
            self._extract_json_text(
                response
            )
        )

        payload = self._parse_json(
            response_text
        )

        try:
            return (
                ProcedureValidationResult
                .model_validate(
                    payload
                )
            )

        except ValidationError as exc:
            raise RuntimeError(
                f"{definition.name} "
                f"v{definition.version} "
                "devolvió un JSON que no cumple "
                "el contrato "
                "ProcedureValidationResult."
            ) from exc

    def get_azure_operations_agent(
        self,
    ) -> FoundryAgent:
        """
        Obtiene agent-azure-operations-sbx utilizando
        exclusivamente la definición efectiva
        del catálogo.

        Este método NO ejecuta todavía ninguna operación.

        La ejecución real queda controlada por el
        IncidentResolutionWorkflow después de:

        - ProcedureRuntime;
        - HITL;
        - ApprovedProcedureStep;
        - routing determinista post-HITL.
        """

        definition = self.get_definition(
            AgentKey.AZURE_OPERATIONS
        )

        self._register_invocation(
            definition
        )

        return self._create_agent(
            definition
        )

    async def begin_azure_operations(
        self,
        message: str,
    ) -> AzureOperationsInvocation:
        """
        Inicia una única ejecución Azure Operations
        con una AgentSession dedicada.

        La sesión permite continuar posteriormente
        una solicitud de aprobación MCP sin crear
        otra ejecución lógica desde cero.

        Este método:

        - NO aprueba ninguna tool;
        - NO interpreta la respuesta;
        - NO decide autorización;
        - NO ejecuta PreCallSecurity.
        """

        definition = self.get_definition(
            AgentKey.AZURE_OPERATIONS
        )

        self._register_invocation(
            definition
        )

        agent = self._create_agent(
            definition
        )

        session = agent.create_session()

        if session is None:
            raise RuntimeError(
                "FoundryAgent no creó una "
                "AgentSession válida."
            )

        response = await agent.run(
            message,
            session=session,
            options=ChatOptions(
                store=True
            ),
        )

        return AzureOperationsInvocation(
            agent=agent,
            session=session,
            response=response,
            owner_token=(
                self
                ._azure_operations_owner_token
            ),
        )

    async def continue_azure_operations(
        self,
        *,
        invocation: AzureOperationsInvocation,
        approval_request,
        approved: bool,
    ) -> AzureOperationsInvocation:
        """
        Continúa exactamente una ejecución Azure
        Operations ya iniciada.

        Reutiliza:

        - la misma instancia de FoundryAgent;
        - la misma AgentSession.

        approval_request debe ser el Content nativo
        devuelto por Agent Framework.

        Este método NO decide si la solicitud debe
        aprobarse. Recibe esa decisión después de
        que la capa gobernante la haya validado.
        """

        if not isinstance(
            invocation,
            AzureOperationsInvocation,
        ):
            raise ValueError(
                "Azure Operations continuation "
                "requiere AzureOperationsInvocation."
            )

        if (
            invocation.owner_token
            is not self
            ._azure_operations_owner_token
        ):
            raise ValueError(
                "AzureOperationsInvocation no "
                "pertenece a esta instancia "
                "FoundryAgents."
            )

        if invocation.agent is None:
            raise ValueError(
                "AzureOperationsInvocation no "
                "contiene agente."
            )

        if invocation.session is None:
            raise ValueError(
                "AzureOperationsInvocation no "
                "contiene sesión."
            )

        if not isinstance(
            approved,
            bool,
        ):
            raise ValueError(
                "approved debe ser bool."
            )

        approval_factory = getattr(
            approval_request,
            "to_function_approval_response",
            None,
        )

        if not callable(
            approval_factory
        ):
            raise ValueError(
                "La solicitud no permite generar "
                "una respuesta de aprobación "
                "Agent Framework."
            )

        #
        # IMPORTANTE:
        # la conversión sólo ocurre DESPUÉS de
        # validar el contexto de ejecución.
        #
        approval_response = (
            approval_factory(
                approved
            )
        )

        approval_message = Message(
            role="user",
            contents=[
                approval_response
            ],
        )

        response = await invocation.agent.run(
            [
                approval_message
            ],
            session=invocation.session,
            options=ChatOptions(
                store=True
            ),
        )

        return AzureOperationsInvocation(
            agent=invocation.agent,
            session=invocation.session,
            response=response,
            owner_token=(
                invocation.owner_token
            ),
        )

    async def run_azure_operations(
        self,
        message: str,
    ):
        """
        Invoca agent-azure-operations-sbx utilizando
        exclusivamente la definición efectiva
        del catálogo.

        IMPORTANTE:

        Este agente puede utilizar tools/MCP
        configurados server-side en Microsoft Foundry
        y, por tanto, su ejecución puede provocar
        interacciones reales contra Azure.

        Este método NO decide:

        - si la operación está aprobada;
        - si el paso pertenece al dominio Azure;
        - el routing;
        - el recurso autorizado;
        - la operación autorizada;
        - los parámetros autorizados;
        - la política pre-call.

        Esas responsabilidades pertenecen al
        workflow determinista y a las fases de
        seguridad correspondientes.

        Durante FASE 13 devuelve deliberadamente
        la respuesta nativa de Agent Framework.

        No intenta:

        - extraer JSON;
        - reparar respuestas;
        - convertir el resultado a AzureOperationResult;
        - aprobar automáticamente solicitudes MCP.

        Esto permite inspeccionar correctamente
        respuestas MCP y posibles
        mcp_approval_request antes de formalizar
        el contrato operacional definitivo.
        """

        definition = self.get_definition(
            AgentKey.AZURE_OPERATIONS
        )

        self._register_invocation(
            definition
        )

        agent = self._create_agent(
            definition
        )

        return await agent.run(
            message
        )

    def get_classification_definition(
        self,
    ) -> FoundryAgentDefinition:
        """
        Devuelve la definición versionada del agente
        de clasificación.

        Todavía no realiza la invocación.
        """

        return self.get_definition(
            AgentKey.CLASSIFICATION
        )

    def get_knowledge_definition(
        self,
    ) -> FoundryAgentDefinition:
        """
        Devuelve la definición versionada del agente
        de conocimiento.

        Todavía no realiza la invocación.
        """

        return self.get_definition(
            AgentKey.KNOWLEDGE
        )

    def get_itsm_definition(
        self,
    ) -> FoundryAgentDefinition:
        """
        Devuelve la definición versionada del
        agente ITSM.

        La integración real con el backend ITSM
        permanece pendiente.
        """

        return self.get_definition(
            AgentKey.ITSM
        )