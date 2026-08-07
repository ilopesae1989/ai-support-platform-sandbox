import os
from dataclasses import dataclass

from agent_framework.foundry import FoundryAgent
from azure.identity import AzureCliCredential

from .contracts import (
    AlertTriageResult,
    ProcedureExecutionResult,
)


@dataclass(frozen=True)
class FoundryAgentDefinition:
    name: str
    version: str | None = None


class FoundryAgents:
    """
    Adaptadores hacia Prompt Agents administrados en Microsoft Foundry.

    Este componente:

    - NO define instrucciones;
    - NO añade herramientas;
    - NO añade MCP;
    - NO modifica Knowledge;
    - NO decide routing;
    - NO mantiene estado de workflow.

    Las definiciones de los agentes siguen residiendo en Foundry.
    """

    def __init__(
        self,
        project_endpoint: str | None = None,
    ) -> None:
        self._project_endpoint = (
            project_endpoint
            or os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        )

        if not self._project_endpoint:
            raise ValueError(
                "FOUNDRY_PROJECT_ENDPOINT no está configurado."
            )

        # Para desarrollo local.
        # En producción lo sustituiremos por ManagedIdentityCredential.
        self._credential = AzureCliCredential()

    def _create_agent(
        self,
        definition: FoundryAgentDefinition,
    ) -> FoundryAgent:
        return FoundryAgent(
            project_endpoint=self._project_endpoint,
            agent_name=definition.name,
            agent_version=definition.version,
            credential=self._credential,
            timeout=120.0,
        )

    async def run_alert_triage(
        self,
        message: str,
        *,
        agent_version: str | None = None,
    ) -> AlertTriageResult:
        agent = self._create_agent(
            FoundryAgentDefinition(
                name="agent-alert-triage-sbx",
                version=agent_version,
            )
        )

        response = await agent.run(
            message,
            options={
                "response_format": AlertTriageResult,
            },
        )

        if response.value is None:
            raise RuntimeError(
                "agent-alert-triage-sbx no devolvió "
                "una salida estructurada válida."
            )

        return AlertTriageResult.model_validate(
            response.value
        )

    async def run_procedure_execution(
        self,
        message: str,
        *,
        agent_version: str | None = None,
    ) -> ProcedureExecutionResult:
        agent = self._create_agent(
            FoundryAgentDefinition(
                name="agent-procedure-execution-sbx",
                version=agent_version,
            )
        )

        response = await agent.run(
            message,
            options={
                "response_format": ProcedureExecutionResult,
            },
        )

        if response.value is None:
            raise RuntimeError(
                "agent-procedure-execution-sbx no devolvió "
                "una salida estructurada válida."
            )

        return ProcedureExecutionResult.model_validate(
            response.value
        )

    def get_azure_operations_agent(
        self,
        *,
        agent_version: str | None = None,
    ) -> FoundryAgent:
        """
        Devuelve el agente operativo Azure administrado en Foundry.

        No se ejecuta aquí ninguna operación.
        La invocación real quedará controlada por el workflow.
        """
        return self._create_agent(
            FoundryAgentDefinition(
                name="agent-azure-operations-sbx",
                version=agent_version,
            )
        )