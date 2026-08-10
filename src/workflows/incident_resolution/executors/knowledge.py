from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
)

from src.agents.foundry_agents import (
    FoundryAgents,
)
from src.workflows.incident_resolution.models import (
    ClassifiedAlertContext,
    KnowledgeEnrichedAlertContext,
)


class KnowledgeExecutor(Executor):
    """
    Adaptador de workflow para el Knowledge Agent.

    Responsabilidades:
    - recibir alerta + clasificación;
    - construir una consulta mínima y controlada;
    - invocar agent-knowledge-sbx mediante FoundryAgents;
    - recibir KnowledgeResult ya validado;
    - conservar el contexto anterior;
    - enviarlo al siguiente executor.

    No evalúa procedure_match.
    No decide execution_eligible.
    No decide criticidad.
    No realiza routing.
    No ejecuta operaciones.
    """

    def __init__(
        self,
        agents: FoundryAgents,
    ) -> None:
        super().__init__(
            id="knowledge"
        )

        self._agents = agents

    @handler
    async def retrieve_knowledge(
        self,
        context: ClassifiedAlertContext,
        ctx: WorkflowContext[
            KnowledgeEnrichedAlertContext
        ],
    ) -> None:
        prompt = self._build_prompt(
            context
        )

        result = await self._agents.run_knowledge(
            prompt
        )

        await ctx.send_message(
            KnowledgeEnrichedAlertContext(
                alert=context.alert,
                classification=context.classification,
                knowledge=result,
            )
        )

    @staticmethod
    def _build_prompt(
        context: ClassifiedAlertContext,
    ) -> str:
        alert = context.alert
        classification = context.classification

        affected_resource = (
            alert.affected_resource
            or classification.affected_resource
            or "no especificado"
        )

        resource_type = (
            alert.resource_type
            or "no especificado"
        )

        affected_service = (
            classification.affected_service
            or alert.service
            or "no especificado"
        )

        return f"""
Busca en el conocimiento corporativo disponible documentación relacionada con la siguiente incidencia:

AlertId: {alert.alert_id}

Clasificación técnica:
alert_classification: {classification.alert_classification}
technical_domain: {classification.technical_domain}

Recurso:
{affected_resource}

Tipo de recurso:
{resource_type}

Servicio afectado:
{affected_service}

Incidencia:
{alert.description}

Recupera únicamente información respaldada por la base de conocimiento corporativa.

Devuelve exclusivamente la respuesta estructurada definida por tus instrucciones.
""".strip()