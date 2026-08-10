from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
)

from src.agents.foundry_agents import (
    FoundryAgents,
)
from src.workflows.incident_resolution.models import (
    KnowledgeEnrichedAlertContext,
    TriagedAlertContext,
)


class AlertTriageExecutor(Executor):
    """
    Adaptador de workflow para el Alert Triage Agent.

    Responsabilidades:
    - recibir alerta + clasificación + conocimiento;
    - construir una petición controlada;
    - invocar agent-alert-triage-sbx mediante FoundryAgents;
    - recibir AlertTriageResult ya validado;
    - conservar toda la cadena cognitiva previa;
    - emitir TriagedAlertContext al siguiente executor.

    No ejecuta procedimientos.
    No ejecuta operaciones.
    No realiza HITL.
    No llama a MCP.
    No decide el routing del workflow.
    No modifica el resultado del agente.
    """

    def __init__(
        self,
        agents: FoundryAgents,
    ) -> None:
        super().__init__(
            id="alert_triage"
        )

        self._agents = agents

    @handler
    async def triage_alert(
        self,
        context: KnowledgeEnrichedAlertContext,
        ctx: WorkflowContext[
            TriagedAlertContext
        ],
    ) -> None:
        prompt = self._build_prompt(
            context
        )

        result = await self._agents.run_alert_triage(
            prompt
        )

        await ctx.send_message(
            TriagedAlertContext(
                alert=context.alert,
                classification=context.classification,
                knowledge=context.knowledge,
                triage=result,
            )
        )

    @staticmethod
    def _build_prompt(
        context: KnowledgeEnrichedAlertContext,
    ) -> str:
        alert = context.alert
        classification = context.classification
        knowledge = context.knowledge

        affected_resource = (
            classification.affected_resource
            or alert.affected_resource
            or "no especificado"
        )

        affected_service = (
            classification.affected_service
            or alert.service
            or "no especificado"
        )

        resource_type = (
            alert.resource_type
            or "no especificado"
        )

        source_severity = (
            alert.source_severity
            or "no especificada"
        )

        documents_text = (
            "\n".join(
                (
                    f"- {document.id or 'sin-id'}"
                    f" — {document.name}"
                    f" {document.version or ''}\n"
                    f"  {document.relevance_summary}"
                )
                for document in knowledge.documents
            )
            if knowledge.documents
            else (
                "No se ha encontrado información "
                "validada aplicable en la base "
                "de conocimiento corporativa."
            )
        )

        limitations_text = (
            "\n".join(
                f"- {limitation}"
                for limitation in knowledge.limitations
            )
            if knowledge.limitations
            else (
                "Ninguna limitación adicional "
                "documentada."
            )
        )

        knowledge_summary = (
            knowledge.knowledge_summary
            or "No disponible."
        )

        return f"""
Analiza la siguiente alerta:

Origen: {alert.source}
AlertId: {alert.alert_id}
Nombre: {alert.name}
Severidad origen: {source_severity}
Recurso: {affected_resource}
Tipo de recurso: {resource_type}
Descripción: {alert.description}

Clasificación previa:
alert_classification: {classification.alert_classification}
technical_domain: {classification.technical_domain}
affected_resource: {affected_resource}
affected_service: {affected_service}

Conocimiento corporativo recuperado:

{documents_text}

Resumen del conocimiento:
{knowledge_summary}

Limitaciones de la recuperación:
{limitations_text}

Clasifica la alerta utilizando exclusivamente los procedimientos
y matrices corporativas disponibles.

Devuelve únicamente la respuesta estructurada definida por tus
instrucciones.
""".strip()