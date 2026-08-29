from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
)

from src.agents.foundry_agents import (
    FoundryAgents,
)
from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)
from src.workflows.incident_resolution.models import (
    ClassifiedAlertContext,
)

from src.workflows.incident_resolution.workflow_input import (
    IncidentWorkflowInput,
    store_incident_conversation_id,
)


class ClassificationExecutor(Executor):
    """
    Adaptador de workflow para el Classification Agent.

    Responsabilidades:
    - recibir una NormalizedAlert;
    - construir una petición mínima y controlada;
    - invocar agent-classification-sbx mediante FoundryAgents;
    - recibir ClassificationResult ya validado;
    - conservar la alerta original;
    - enviar ClassifiedAlertContext al siguiente executor.

    No realiza routing.
    No consulta Knowledge.
    No selecciona procedimientos.
    No decide criticidad corporativa.
    No ejecuta operaciones.
    """

    def __init__(
        self,
        agents: FoundryAgents,
    ) -> None:
        super().__init__(
            id="classification"
        )

        self._agents = agents

    @handler
    async def classify_workflow_input(
        self,
        workflow_input: IncidentWorkflowInput,
        ctx: WorkflowContext[
            ClassifiedAlertContext
        ],
    ) -> None:
        """
        Adapta el envelope replayable al pipeline
        cognitivo existente.

        conversation_id se guarda únicamente en
        workflow state.

        El agente continúa recibiendo sólo
        NormalizedAlert.
        """

        store_incident_conversation_id(
            ctx,
            workflow_input.conversation_id,
        )

        await self.classify_alert(
            workflow_input.alert,
            ctx,
        )

    @handler
    async def classify_alert(
        self,
        alert: NormalizedAlert,
        ctx: WorkflowContext[
            ClassifiedAlertContext
        ],
    ) -> None:
        prompt = self._build_prompt(
            alert
        )

        result = await self._agents.run_classification(
            prompt
        )

        await ctx.send_message(
            ClassifiedAlertContext(
                alert=alert,
                classification=result,
            )
        )

    @staticmethod
    def _build_prompt(
        alert: NormalizedAlert,
    ) -> str:
        """
        Construye únicamente el contexto necesario
        para Classification.

        raw_attributes no se propaga al Prompt Agent.
        """

        source_event_id = (
            alert.source_event_id
            or "no especificado"
        )

        source_severity = (
            alert.source_severity
            or "no especificada"
        )

        timestamp = (
            alert.timestamp.isoformat()
            if alert.timestamp is not None
            else "no especificado"
        )

        affected_resource = (
            alert.affected_resource
            or "no especificado"
        )

        resource_type = (
            alert.resource_type
            or "no especificado"
        )

        service = (
            alert.service
            or "no especificado"
        )

        environment = (
            alert.environment
            or "no especificado"
        )

        return f"""
Clasifica la siguiente alerta operativa normalizada.

AlertId: {alert.alert_id}
Origen: {alert.source}
SourceEventId: {source_event_id}
Nombre: {alert.name}
Severidad origen: {source_severity}
Timestamp: {timestamp}
Recurso: {affected_resource}
Tipo de recurso: {resource_type}
Servicio: {service}
Entorno: {environment}

Descripción:
{alert.description}

Devuelve únicamente la respuesta estructurada definida por tus instrucciones.
""".strip()