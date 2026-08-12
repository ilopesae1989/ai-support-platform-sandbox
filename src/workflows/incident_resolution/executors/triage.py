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

        operational_parameter_availability = {
            "subscription_id": (
                alert.subscription_id
                is not None
                and bool(
                    alert.subscription_id.strip()
                )
            ),

            "resource_group": (
                alert.resource_group
                is not None
                and bool(
                    alert.resource_group.strip()
                )
            ),

            "vm_name": (
                alert.vm_name
                is not None
                and bool(
                    alert.vm_name.strip()
                )
            ),

            "tenant_id": (
                alert.tenant_id
                is not None
                and bool(
                    alert.tenant_id.strip()
                )
            ),
        }

        available_operational_parameters = [
            parameter_name
            for parameter_name, available
            in operational_parameter_availability.items()
            if available
        ]

        missing_operational_parameters = [
            parameter_name
            for parameter_name, available
            in operational_parameter_availability.items()
            if not available
        ]

        available_operational_text = (
            ", ".join(
                available_operational_parameters
            )
            if available_operational_parameters
            else "ninguno"
        )

        missing_operational_text = (
            ", ".join(
                missing_operational_parameters
            )
            if missing_operational_parameters
            else "ninguno"
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

Disponibilidad de contexto operacional tipado:

Parámetros disponibles:
{available_operational_text}

Parámetros no disponibles:
{missing_operational_text}

Reglas sobre este contexto:

- Esta sección indica exclusivamente disponibilidad.
- No contiene los valores operacionales autorizados.
- No inventes valores para ningún parámetro.
- No reconstruyas subscription_id, resource_group, vm_name ni tenant_id.
- La resolución de los valores exactos se realiza posteriormente
    mediante las capas deterministas Python.
- Utiliza esta información únicamente para determinar si el contexto
    requerido por el procedimiento está disponible.

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

Frontera de responsabilidad para execution_eligible:

- Evalúa si existe un procedimiento corporativo aplicable a la
    incidencia y si el contexto operacional requerido por dicho
    procedimiento está disponible.

- La autenticación y los permisos RBAC del backend de ejecución
    no forman parte de la cobertura documental del procedimiento.

- Si existe un procedimiento exacto que identifica la operación,
    sus parámetros requeridos y su criterio de verificación, no
    marques execution_eligible=false únicamente porque la
    documentación no describa credenciales o roles RBAC.

- La autorización técnica efectiva se valida posteriormente por
    las capas deterministas de seguridad y por el backend autorizado.

- La aprobación humana HITL tampoco es un prerrequisito disponible
    durante Triage. La aprobación se solicita posteriormente por el
    workflow, después de preparar el procedimiento y antes de la
    ejecución externa.

- No marques execution_eligible=false únicamente porque todavía no
    exista approval_id, ticket de aprobación, confirmación humana o
    evidencia de aprobación.

- Si el procedimiento exige aprobación humana antes de una operación
    WRITE, interpreta esa exigencia como una barrera posterior de
    ejecución gestionada por el workflow, no como missing_context de
    Triage.

- Un rechazo posterior del HITL impedirá la ejecución, pero no cambia
    que el procedimiento pueda ser exacto y elegible en esta etapa.

- Sí debes marcar execution_eligible=false cuando falte información
    operacional que el propio procedimiento necesite para determinar
    o parametrizar la operación, cuando exista un bloqueo explícito
    de política, cuando no se pueda determinar el paso aplicable o
    cuando el procedimiento no sea exacto.

- No inventes credenciales, permisos, parámetros ni precondiciones.

Clasifica la alerta utilizando exclusivamente los procedimientos
y matrices corporativas disponibles.

Devuelve únicamente la respuesta estructurada definida por tus
instrucciones.
""".strip()