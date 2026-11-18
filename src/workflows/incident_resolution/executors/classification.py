from agent_framework import (
    Executor,
    WorkflowContext,
    handler,
)

from src.agents.foundry_agents import (
    FoundryAgents,
)
from src.runtime.execution_affinity import AFFINITY_STATE_KEY, ExecutionAffinity
from src.runtime.incident_execution import EXECUTION_ID_STATE_KEY, IncidentExecutionStore
from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)
from src.workflows.incident_resolution.models import (
    ClassifiedAlertContext,
)

from src.workflows.incident_resolution.workflow_input import (
    IncidentWorkflowInput,
    AdmittedIncidentWorkflowInput,
    incident_input_fingerprint,
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
        *,
        id: str = "classification",
        execution_affinity: ExecutionAffinity | None = None,
        execution_store: IncidentExecutionStore | None = None,
    ) -> None:
        super().__init__(
            id=id,
        )

        self._agents = agents
        if execution_affinity is not None and type(execution_affinity) is not ExecutionAffinity:
            raise TypeError("execution_affinity must be ExecutionAffinity.")
        self._execution_affinity = execution_affinity
        if execution_store is not None and (
                not isinstance(execution_store, IncidentExecutionStore)
                or execution_store.execution_affinity != execution_affinity):
            raise ValueError("Execution store must match the graph affinity.")
        self._execution_store = execution_store

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

        if self._execution_store is not None:
            if not isinstance(workflow_input, AdmittedIncidentWorkflowInput):
                raise ValueError("Durable admission is required before the first agent.")
            record = self._execution_store.get_execution(workflow_input.execution_id)
            if (record.affinity != self._execution_affinity
                    or record.input_sha256 != incident_input_fingerprint(workflow_input)):
                raise ValueError("Incident input differs from its admitted execution.")
            existing = ctx.get_state(EXECUTION_ID_STATE_KEY, None)
            if existing is not None and existing != record.execution_id:
                raise ValueError("Incident execution identity changed.")
            ctx.set_state(EXECUTION_ID_STATE_KEY, record.execution_id)
        elif isinstance(workflow_input, AdmittedIncidentWorkflowInput):
            raise ValueError("An admitted input requires its execution store.")
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
        if self._execution_store is not None and ctx.get_state(EXECUTION_ID_STATE_KEY, None) is None:
            raise ValueError("An admitted workflow input is required.")
        if self._execution_affinity is not None:
            document = self._execution_affinity.to_document()
            existing = ctx.get_state(AFFINITY_STATE_KEY, None)
            if existing is not None and existing != document:
                raise ValueError("Incident state contains a different execution affinity.")
            ctx.set_state(AFFINITY_STATE_KEY, document)
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
