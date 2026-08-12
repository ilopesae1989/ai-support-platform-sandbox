from datetime import datetime, timezone

import pytest

from src.agents.contracts import (
    AlertTriageResult,
    ClassificationResult,
    KnowledgeResult,
)
from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)
from src.workflows.incident_resolution.executors.triage import (
    AlertTriageExecutor,
)
from src.workflows.incident_resolution.models import (
    KnowledgeEnrichedAlertContext,
    TriagedAlertContext,
)


class FakeFoundryAgents:
    """
    Sustituye exclusivamente la llamada real
    a agent-alert-triage-sbx.
    """

    def __init__(self) -> None:
        self.received_message: str | None = None

    async def run_alert_triage(
        self,
        message: str,
    ) -> AlertTriageResult:
        self.received_message = message

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
                    "Availability Group AG-PROD ha "
                    "dejado de sincronizarse."
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
                    "name":
                        "SQL AlwaysOn_Rol Change Alerta",
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
                        "SQL AlwaysOn_Rol Change Alerta v1.1"
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
                "confidence": 0.85,
                "ai_opinion": None,
            }
        )

def create_vm_context(
) -> KnowledgeEnrichedAlertContext:
    alert = NormalizedAlert(
        alert_id="ALT-AZ-VM-001",
        source="azure_monitor",
        name="Azure VM stopped",
        description=(
            "La máquina virtual se encuentra "
            "en PowerState/stopped."
        ),
        source_severity="Critical",

        affected_resource=(
            "vm-test-01"
        ),

        resource_type=(
            "Microsoft.Compute/"
            "virtualMachines"
        ),

        service=(
            "Azure Virtual Machines"
        ),

        environment="sandbox",

        subscription_id=(
            "sub-test-001"
        ),

        resource_group=(
            "rg-test"
        ),

        vm_name=(
            "vm-test-01"
        ),

        tenant_id=None,

        correlation_id=(
            "corr-vm-001"
        ),

        raw_attributes={
            "untrusted_subscription":
                "must-not-leak"
        },
    )

    classification = (
        ClassificationResult.model_validate(
            {
                "alert_id":
                    "ALT-AZ-VM-001",

                "alert_classification":
                    "azure_vm_stopped_allocated",

                "technical_domain":
                    "azure",

                "affected_resource":
                    "vm-test-01",

                "affected_service":
                    "Azure Virtual Machines",

                "classification_summary":
                    "VM stopped.",

                "requires_clarification":
                    False,

                "missing_information":
                    [],

                "confidence":
                    0.95,
            }
        )
    )

    knowledge = (
        KnowledgeResult.model_validate(
            {
                "alert_id":
                    "ALT-AZ-VM-001",

                "knowledge_found":
                    True,

                "documents": [
                    {
                        "id":
                            "NTTSY-SBX-AZ-VM-001",

                        "name": (
                            "Arranque de máquina "
                            "virtual Azure en estado "
                            "Stopped (Allocated)"
                        ),

                        "version":
                            "1.0",

                        "relevance_summary": (
                            "Procedimiento exacto "
                            "para VM stopped."
                        ),
                    },
                ],

                "knowledge_summary": (
                    "Existe procedimiento "
                    "operacional exacto."
                ),

                "limitations":
                    [],

                "confidence":
                    0.9,
            }
        )
    )

    return KnowledgeEnrichedAlertContext(
        alert=alert,
        classification=classification,
        knowledge=knowledge,
    )

def test_triage_prompt_exposes_only_operational_parameter_availability():
    context = (
        create_vm_context()
    )

    prompt = (
        AlertTriageExecutor
        ._build_prompt(
            context
        )
    )

    normalized_prompt = (
        " ".join(
            prompt.split()
        )
    )

    assert (
        "subscription_id"
        in prompt
    )

    assert (
        "resource_group"
        in prompt
    )

    assert (
        "vm_name"
        in prompt
    )

    assert (
        "tenant_id"
        in prompt
    )

    assert (
        "subscription_id, "
        "resource_group, vm_name"
        in normalized_prompt
    )

    assert (
        "Parámetros no disponibles: "
        "tenant_id"
        in normalized_prompt
    )

    assert (
        "sub-test-001"
        not in prompt
    )

    assert (
        "rg-test"
        not in prompt
    )

    assert (
        "must-not-leak"
        not in prompt
    )


class FakeWorkflowContext:
    def __init__(self) -> None:
        self.messages = []

    async def send_message(
        self,
        message,
    ) -> None:
        self.messages.append(
            message
        )


def create_context() -> KnowledgeEnrichedAlertContext:
    alert = NormalizedAlert(
        alert_id="ALT-SQL-AG-001",
        source="scom",
        source_event_id="SCOM-001",
        name=(
            "Availability Group Replica "
            "Not Synchronizing"
        ),
        description=(
            "La réplica secundaria del Availability "
            "Group AG-PROD ha dejado de sincronizarse "
            "con la réplica primaria durante más "
            "de 10 minutos."
        ),
        source_severity="Critical",
        timestamp=datetime(
            2026,
            8,
            8,
            12,
            0,
            tzinfo=timezone.utc,
        ),
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
        correlation_id="corr-sql-001",
        raw_attributes={
            "native_secret":
                "must-not-leak"
        },
    )

    classification = ClassificationResult.model_validate(
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
                "Réplica secundaria fuera "
                "de sincronización."
            ),
            "requires_clarification": False,
            "missing_information": [],
            "confidence": 0.95,
        }
    )

    knowledge = KnowledgeResult.model_validate(
        {
            "alert_id": "ALT-SQL-AG-001",
            "knowledge_found": True,
            "documents": [
                {
                    "id": "NTTSY-PRO-016",
                    "name":
                        "SQL AlwaysOn_Rol Change Alerta",
                    "version": "v1.1",
                    "relevance_summary": (
                        "Contiene comprobaciones "
                        "específicas para Always On."
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
                        "adicionales de infraestructura."
                    ),
                },
                {
                    "id": "NTTSY-PRO-020",
                    "name":
                        "Alertas SQL Server",
                    "version": "v1.1",
                    "relevance_summary": (
                        "Contiene comprobaciones "
                        "generales de SQL Server."
                    ),
                },
            ],
            "knowledge_summary": (
                "La documentación contiene "
                "comprobaciones específicas para "
                "Availability Groups."
            ),
            "limitations": [],
            "confidence": 0.88,
        }
    )

    return KnowledgeEnrichedAlertContext(
        alert=alert,
        classification=classification,
        knowledge=knowledge,
    )


@pytest.mark.asyncio
async def test_triage_executor_emits_context():
    agents = FakeFoundryAgents()

    executor = AlertTriageExecutor(
        agents=agents,
    )

    ctx = FakeWorkflowContext()

    original = create_context()

    await executor.triage_alert(
        original,
        ctx,
    )

    assert len(ctx.messages) == 1

    context = ctx.messages[0]

    assert isinstance(
        context,
        TriagedAlertContext,
    )

    #
    # Se conserva la alerta original.
    #
    assert (
        context.alert.alert_id
        == "ALT-SQL-AG-001"
    )

    assert (
        context.alert.correlation_id
        == "corr-sql-001"
    )

    #
    # Se conserva Classification.
    #
    assert (
        context.classification.alert_classification
        == "availability_group_replica_out_of_sync"
    )

    #
    # Se conserva Knowledge.
    #
    assert context.knowledge.knowledge_found is True

    assert (
        context.knowledge.documents[0].id
        == "NTTSY-PRO-016"
    )

    #
    # Se añade Triage.
    #
    result = context.triage

    assert isinstance(
        result,
        AlertTriageResult,
    )

    assert result.procedure_found is True
    assert result.procedure_match == "exact"
    assert result.execution_eligible is True

    assert (
        result.recommended_next_step
        == "procedure_execution"
    )

    assert result.procedure is not None

    assert (
        result.procedure.id
        == "NTTSY-PRO-016"
    )


@pytest.mark.asyncio
async def test_triage_executor_builds_expected_prompt():
    agents = FakeFoundryAgents()

    executor = AlertTriageExecutor(
        agents=agents,
    )

    ctx = FakeWorkflowContext()

    await executor.triage_alert(
        create_context(),
        ctx,
    )

    assert agents.received_message is not None

    prompt = agents.received_message

    normalized_prompt = " ".join(
        prompt.split()
    )

    assert "ALT-SQL-AG-001" in prompt

    assert (
        "availability_group_replica_out_of_sync"
        in prompt
    )

    assert "database" in prompt
    assert "SQLPROD01" in prompt

    assert "NTTSY-PRO-016" in prompt
    assert "NTTSY-PRO-017" in prompt
    assert "NTTSY-PRO-020" in prompt

    assert (
        "La autenticación y los permisos RBAC "
        "del backend de ejecución"
        in normalized_prompt
    )

    assert (
        "no forman parte de la cobertura "
        "documental del procedimiento"
        in normalized_prompt
    )

    assert (
        "no marques execution_eligible=false"
        in normalized_prompt
    )

    assert (
        "únicamente porque la documentación "
        "no describa credenciales o roles RBAC"
        in normalized_prompt
    )

    assert (
        "La autorización técnica efectiva "
        "se valida posteriormente"
        in normalized_prompt
    )

    assert (
        "La aprobación humana HITL"
        in normalized_prompt
    )

    assert (
        "prerrequisito"
        in normalized_prompt
    )

    assert (
        "durante Triage"
        in normalized_prompt
    )

    assert (
        "approval_id"
        in normalized_prompt
    )

    assert (
        "barrera posterior de ejecución"
        in normalized_prompt
    )


@pytest.mark.asyncio
async def test_triage_executor_does_not_leak_raw_attributes():
    agents = FakeFoundryAgents()

    executor = AlertTriageExecutor(
        agents=agents,
    )

    ctx = FakeWorkflowContext()

    await executor.triage_alert(
        create_context(),
        ctx,
    )

    assert agents.received_message is not None

    prompt = agents.received_message

    assert "native_secret" not in prompt
    assert "must-not-leak" not in prompt


@pytest.mark.asyncio
async def test_triage_executor_preserves_agent_result():
    agents = FakeFoundryAgents()

    executor = AlertTriageExecutor(
        agents=agents,
    )

    ctx = FakeWorkflowContext()

    await executor.triage_alert(
        create_context(),
        ctx,
    )

    context = ctx.messages[0]

    result = context.triage

    assert result.confidence == 0.85

    assert result.missing_context == []

    assert (
        result.knowledge_coverage
        == "complete"
    )

    assert (
        result.corporate_criticality
        == "unknown"
    )

    assert (
        result.criticality_source
        == "unknown"
    )

    assert result.escalation.required is False


@pytest.mark.asyncio
async def test_triage_executor_preserves_previous_context():
    agents = FakeFoundryAgents()

    executor = AlertTriageExecutor(
        agents=agents,
    )

    ctx = FakeWorkflowContext()

    original = create_context()

    await executor.triage_alert(
        original,
        ctx,
    )

    enriched = ctx.messages[0]

    assert enriched.alert == original.alert

    assert (
        enriched.classification
        == original.classification
    )

    assert (
        enriched.knowledge
        == original.knowledge
    )