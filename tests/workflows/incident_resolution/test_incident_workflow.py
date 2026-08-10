import pytest

from src.agents.contracts import (
    AlertTriageResult,
    ClassificationResult,
    KnowledgeResult,
    ProcedureExecutionResult,
)
from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)
from src.workflows.incident_resolution.workflow import (
    build_incident_resolution_workflow,
)


class FakeFoundryAgents:
    """
    Sustituye exclusivamente las llamadas remotas
    a Microsoft Foundry.

    El Workflow, los executors, el routing,
    ProcedureRuntime, la política y HITL son reales.

    Simula los contratos reales de:

    - agent-classification-sbx v7
    - agent-knowledge-sbx v8
    - agent-alert-triage-sbx v9
    - agent-procedure-execution-sbx v5
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

        self.classification_prompt: str | None = None
        self.knowledge_prompt: str | None = None
        self.triage_prompt: str | None = None
        self.procedure_prompt: str | None = None

    async def run_classification(
        self,
        message: str,
        *,
        agent_version: str | None = None,
    ) -> ClassificationResult:
        self.calls.append(
            "classification"
        )

        self.classification_prompt = message

        return ClassificationResult.model_validate(
            {
                "alert_id": "ALT-SQL-AG-001",
                "alert_classification":
                    "availability_group_replica_out_of_sync",
                "technical_domain": "database",
                "affected_resource": "SQLPROD01",
                "affected_service": (
                    "Microsoft SQL Server Always On "
                    "Availability Group"
                ),
                "classification_summary": (
                    "La réplica secundaria del "
                    "Availability Group ha dejado "
                    "de sincronizarse."
                ),
                "requires_clarification": False,
                "missing_information": [],
                "confidence": 0.95,
            }
        )

    async def run_knowledge(
        self,
        message: str,
        *,
        agent_version: str | None = None,
    ) -> KnowledgeResult:
        self.calls.append(
            "knowledge"
        )

        self.knowledge_prompt = message

        return KnowledgeResult.model_validate(
            {
                "alert_id": "ALT-SQL-AG-001",
                "knowledge_found": True,
                "documents": [
                    {
                        "id": "NTTSY-PRO-016",
                        "name": (
                            "SQL AlwaysOn_Rol "
                            "Change Alerta"
                        ),
                        "version": "v1.1",
                        "relevance_summary": (
                            "Contiene comprobaciones "
                            "específicas para SQL Server "
                            "Always On Availability Groups."
                        ),
                    },
                    {
                        "id": "NTTSY-PRO-017",
                        "name": (
                            "Revisión de infraestructura "
                            "de un servidor genérico"
                        ),
                        "version": "v1.3",
                        "relevance_summary": (
                            "Contiene comprobaciones "
                            "adicionales de infraestructura "
                            "y servidores SQL."
                        ),
                    },
                    {
                        "id": "NTTSY-PRO-020",
                        "name": (
                            "Alertas SQL Server"
                        ),
                        "version": "v1.1",
                        "relevance_summary": (
                            "Contiene comprobaciones "
                            "generales de SQL Server "
                            "y criterios de escalado."
                        ),
                    },
                ],
                "knowledge_summary": (
                    "La base de conocimiento contiene "
                    "procedimientos aplicables a problemas "
                    "de sincronización de Availability Groups."
                ),
                "limitations": [],
                "confidence": 0.90,
            }
        )

    async def run_alert_triage(
        self,
        message: str,
        *,
        agent_version: str | None = None,
    ) -> AlertTriageResult:
        self.calls.append(
            "alert_triage"
        )

        self.triage_prompt = message

        return AlertTriageResult.model_validate(
            {
                "alert_classification":
                    "availability_group_replica_out_of_sync",
                "technical_domain": "database",
                "affected_resource": "SQLPROD01",
                "affected_service": (
                    "Microsoft SQL Server Always On "
                    "Availability Group"
                ),
                "technical_summary": (
                    "La réplica secundaria del "
                    "Availability Group AG-PROD "
                    "no está sincronizada."
                ),
                "source_severity": "Critical",
                "corporate_criticality": "unknown",
                "criticality_source": "unknown",
                "procedure_found": True,
                "procedure_match": "exact",
                "execution_eligible": True,
                "knowledge_coverage": "complete",
                "recommended_next_step":
                    "procedure_execution",
                "procedure": {
                    "id": "NTTSY-PRO-016",
                    "name": (
                        "SQL AlwaysOn_Rol "
                        "Change Alerta"
                    ),
                    "version": "v1.1",
                    "resolution_criteria": None,
                },
                "escalation": {
                    "required": False,
                    "team": None,
                    "level": None,
                    "criteria": None,
                },
                "possible_false_positive":
                    "unknown",
                "missing_context": [],
                "source_documents": [
                    (
                        "NTTSY-PRO-016 — "
                        "SQL AlwaysOn_Rol "
                        "Change Alerta v1.1"
                    ),
                    (
                        "NTTSY-PRO-017 — "
                        "Revisión de infraestructura "
                        "de un servidor genérico v1.3"
                    ),
                    (
                        "NTTSY-PRO-020 — "
                        "Alertas SQL Server v1.1"
                    ),
                ],
                "confidence": 0.88,
                "ai_opinion": None,
            }
        )

    async def run_procedure_execution(
        self,
        message: str,
        *,
        agent_version: str | None = None,
    ) -> ProcedureExecutionResult:
        self.calls.append(
            "procedure_execution"
        )

        self.procedure_prompt = message

        return ProcedureExecutionResult.model_validate(
            {
                "alert_id": "ALT-SQL-AG-001",
                "procedure": {
                    "id": "NTTSY-PRO-016",
                    "name": (
                        "SQL AlwaysOn_Rol "
                        "Change Alerta"
                    ),
                    "version": "v1.1",
                },
                "execution_allowed": True,
                "blocked_by_policy": False,
                "total_steps": 5,
                "current_step": 1,
                "step": {
                    "id": "1",
                    "description": (
                        "Conectarse al cluster SQL "
                        "y comprobar el estado de "
                        "sincronización del "
                        "Availability Group."
                    ),
                    "step_type": "validation",
                    "operation_domain": "database",
                    "operation_kind": "read",
                    "target_resource": "SQLPROD01",
                    "required_parameters": [], 
                    "preconditions": [],
                    "expected_result": (
                        "El estado actual de "
                        "sincronización queda "
                        "identificado."
                    ),
                    "verification": (
                        "Validar el estado mediante "
                        "el mecanismo indicado en "
                        "el procedimiento."
                    ),
                },
                "resolution_criteria": None,
                "next_action": "execute_step",
                "escalation": {
                    "required": False,
                    "team": None,
                    "level": None,
                    "criteria": None,
                },
                "requires_clarification": False,
                "missing_information": [],
                "source_documents": [
                    (
                        "NTTSY-PRO-016 - "
                        "SQL AlwaysOn_Rol "
                        "Change Alerta v1.1"
                    )
                ],
                "confidence": 0.95,
            }
        )


def create_alert() -> NormalizedAlert:
    """
    Entrada real del nuevo IncidentResolutionWorkflow.

    Ya no creamos artificialmente
    ProcedureExecutionRequest desde fuera.
    """

    return NormalizedAlert(
        alert_id="ALT-SQL-AG-001",
        source="scom",
        source_event_id="SCOM-AG-001",
        name=(
            "Availability Group Replica "
            "Not Synchronizing"
        ),
        description=(
            "La réplica secundaria del "
            "Availability Group AG-PROD "
            "ha dejado de sincronizarse con "
            "la réplica primaria durante "
            "más de 10 minutos."
        ),
        source_severity="Critical",
        affected_resource="SQLPROD01",
        resource_type=(
            "Microsoft SQL Server Always On "
            "Availability Group"
        ),
        service=(
            "Microsoft SQL Server Always On "
            "Availability Group"
        ),
        environment="production",
        correlation_id="corr-sql-ag-001",
        raw_attributes={
            "native_test_value":
                "must-not-leak"
        },
    )


@pytest.mark.asyncio
async def test_incident_workflow_reaches_approval_from_normalized_alert():
    """
    Demuestra el pipeline completo hasta HITL:

    NormalizedAlert
        ↓
    Classification
        ↓
    Knowledge
        ↓
    Alert Triage
        ↓
    routing exact
        ↓
    ProcedureRequest
        ↓
    Procedure Execution
        ↓
    ProcedureRuntime
        ↓
    Policy
        ↓
    request_info()
    """

    agents = FakeFoundryAgents()

    workflow = build_incident_resolution_workflow(
        agents=agents,
    )

    alert = create_alert()

    approval_requests = []

    async for event in workflow.run(
        alert,
        stream=True,
    ):
        if event.type == "request_info":
            approval_requests.append(
                event
            )

    #
    # Los cuatro agentes cognitivos deben
    # ejecutarse exactamente una vez y en orden.
    #
    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
    ]

    #
    # Debe existir exactamente una solicitud HITL.
    #
    assert len(approval_requests) == 1

    approval_event = approval_requests[0]

    approval = approval_event.data

    #
    # Correlación con la alerta original.
    #
    assert (
        approval.alert_id
        == "ALT-SQL-AG-001"
    )

    #
    # El procedimiento elegido por Triage
    # debe llegar intacto al Runtime.
    #
    assert (
        approval.procedure_id
        == "NTTSY-PRO-016"
    )

    assert approval.current_step == 1

    #
    # El paso debe seguir siendo una operación
    # de lectura del dominio database.
    #
    assert (
        approval.operation_domain
        == "database"
    )

    assert (
        approval.operation_kind
        == "read"
    )

    assert (
        approval.target_resource
        == "SQLPROD01"
    )

    #
    # Debe solicitar aprobación antes de
    # cualquier ejecución técnica.
    #
    assert approval_event.type == "request_info"


@pytest.mark.asyncio
async def test_incident_workflow_preserves_cognitive_input_boundaries():
    """
    Comprueba que raw_attributes de la alerta
    no llegan a los prompts cognitivos.
    """

    agents = FakeFoundryAgents()

    workflow = build_incident_resolution_workflow(
        agents=agents,
    )

    alert = create_alert()

    async for event in workflow.run(
        alert,
        stream=True,
    ):
        if event.type == "request_info":
            break

    assert (
        agents.classification_prompt
        is not None
    )

    assert (
        agents.knowledge_prompt
        is not None
    )

    assert (
        agents.triage_prompt
        is not None
    )

    assert (
        "native_test_value"
        not in agents.classification_prompt
    )

    assert (
        "must-not-leak"
        not in agents.classification_prompt
    )

    assert (
        "native_test_value"
        not in agents.knowledge_prompt
    )

    assert (
        "must-not-leak"
        not in agents.knowledge_prompt
    )

    assert (
        "native_test_value"
        not in agents.triage_prompt
    )

    assert (
        "must-not-leak"
        not in agents.triage_prompt
    )


@pytest.mark.asyncio
async def test_incident_workflow_procedure_receives_triage_selection():
    """
    Comprueba que ProcedureExecution no recibe
    una selección artificial creada por el test.

    Debe recibir la selección producida por
    Alert Triage a través del routing Python.
    """

    agents = FakeFoundryAgents()

    workflow = build_incident_resolution_workflow(
        agents=agents,
    )

    async for event in workflow.run(
        create_alert(),
        stream=True,
    ):
        if event.type == "request_info":
            break

    assert (
        agents.procedure_prompt
        is not None
    )

    prompt = agents.procedure_prompt

    assert "ALT-SQL-AG-001" in prompt

    assert "NTTSY-PRO-016" in prompt

    assert (
        "SQL AlwaysOn_Rol Change Alerta"
        in prompt
    )

    assert "v1.1" in prompt

    assert "procedure_found: true" in prompt

    assert "procedure_match: exact" in prompt

    assert "execution_eligible: true" in prompt

    assert "SQLPROD01" in prompt