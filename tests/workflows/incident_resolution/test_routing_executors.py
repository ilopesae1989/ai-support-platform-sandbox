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
from src.workflows.incident_resolution.executors.routing import (
    KnowledgeReviewExecutor,
    ManualAnalysisExecutor,
    ProcedureRequestExecutor,
)
from src.workflows.incident_resolution.models import (
    KnowledgeReviewRequest,
    ManualAnalysisRequest,
    ProcedureExecutionInput,
    TriagedAlertContext,
)


class FakeWorkflowContext:
    def __init__(self) -> None:
        self.messages = []
        self.outputs = []

    async def send_message(
        self,
        message,
    ) -> None:
        self.messages.append(
            message
        )

    async def yield_output(
        self,
        output,
    ) -> None:
        self.outputs.append(
            output
        )


def create_context(
    *,
    procedure_match: str,
    execution_eligible: bool,
    recommended_next_step: str,
    procedure_found: bool,
    missing_context: list[str] | None = None,
) -> TriagedAlertContext:
    alert = NormalizedAlert(
        alert_id="ALT-TEST-001",
        source="scom",
        source_event_id="SCOM-TEST-001",
        name="Test Alert",
        description=(
            "Alerta utilizada para pruebas de routing."
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
        affected_resource="SERVER01",
        resource_type="TestResource",
        service="Test Service",
        correlation_id="corr-test-001",
    )

    classification = ClassificationResult.model_validate(
        {
            "alert_id": "ALT-TEST-001",
            "alert_classification": "test_alert",
            "technical_domain": "database",
            "affected_resource": "SERVER01",
            "affected_service": "Test Service",
            "classification_summary": "Test.",
            "requires_clarification": False,
            "missing_information": [],
            "confidence": 0.90,
        }
    )

    knowledge = KnowledgeResult.model_validate(
        {
            "alert_id": "ALT-TEST-001",
            "knowledge_found": procedure_found,
            "documents": (
                [
                    {
                        "id": "PROC-001",
                        "name": "Test Procedure",
                        "version": "v1",
                        "relevance_summary": (
                            "Procedimiento usado para testing."
                        ),
                    }
                ]
                if procedure_found
                else []
            ),
            "knowledge_summary": (
                "Existe conocimiento aplicable."
                if procedure_found
                else None
            ),
            "limitations": [],
            "confidence": (
                0.90
                if procedure_found
                else 0.0
            ),
        }
    )

    procedure = (
        {
            "id": "PROC-001",
            "name": "Test Procedure",
            "version": "v1",
            "resolution_criteria": None,
        }
        if procedure_found
        else None
    )

    triage = AlertTriageResult.model_validate(
        {
            "alert_classification": "test_alert",
            "technical_domain": "database",
            "affected_resource": "SERVER01",
            "affected_service": "Test Service",
            "technical_summary": "Test.",
            "source_severity": "Critical",
            "corporate_criticality": "unknown",
            "criticality_source": "unknown",
            "procedure_found": procedure_found,
            "procedure_match": procedure_match,
            "execution_eligible": execution_eligible,
            "knowledge_coverage": (
                "complete"
                if procedure_match == "exact"
                else (
                    "partial"
                    if procedure_match == "partial"
                    else "none"
                )
            ),
            "recommended_next_step":
                recommended_next_step,
            "procedure": procedure,
            "escalation": {
                "required": (
                    recommended_next_step
                    == "human_escalation"
                ),
                "team": None,
                "level": None,
                "criteria": None,
            },
            "possible_false_positive": "unknown",
            "missing_context": (
                missing_context
                if missing_context is not None
                else []
            ),
            "source_documents": (
                ["PROC-001"]
                if procedure_found
                else []
            ),
            "confidence": 0.90,
            "ai_opinion": None,
        }
    )

    return TriagedAlertContext(
        alert=alert,
        classification=classification,
        knowledge=knowledge,
        triage=triage,
    )


@pytest.mark.asyncio
async def test_procedure_request_executor_builds_request():
    executor = ProcedureRequestExecutor()
    ctx = FakeWorkflowContext()

    context = create_context(
        procedure_match="exact",
        execution_eligible=True,
        recommended_next_step="procedure_execution",
        procedure_found=True,
    )

    await executor.prepare_procedure_request(
        context,
        ctx,
    )

    assert len(ctx.messages) == 1
    assert ctx.outputs == []

    result = ctx.messages[0]

    #
    # El executor no envía directamente el request
    # cognitivo.
    #
    # Desde FASE 12 mantiene separados:
    #
    # - request cognitivo;
    # - identidad determinista de ejecución;
    # - OperationalContext autoritativo.
    #
    assert isinstance(
        result,
        ProcedureExecutionInput,
    )

    request = result.request

    assert request.alert_id == "ALT-TEST-001"

    assert request.procedure_found is True
    assert request.procedure_match == "exact"
    assert request.execution_eligible is True

    assert request.procedure_id == "PROC-001"
    assert request.procedure_name == "Test Procedure"
    assert request.procedure_version == "v1"

    assert (
        request.affected_resource
        == "SERVER01"
    )

    assert (
        request.incident_description
        == "Alerta utilizada para pruebas de routing."
    )

    #
    # La identidad de ejecución nace en Python
    # antes de Procedure v5.
    #
    assert (
        result.execution_identity.workflow_id
        .startswith("wf-")
    )

    assert (
        result.execution_identity.alert_id
        == "ALT-TEST-001"
    )

    assert (
        result.execution_identity.correlation_id
        == "corr-test-001"
    )

    #
    # El contexto operacional no procede del LLM.
    #
    assert (
        result.operational_context.alert_id
        == "ALT-TEST-001"
    )

    assert (
        result.operational_context.affected_resource
        == "SERVER01"
    )

    assert (
        result.operational_context.resource_type
        == "TestResource"
    )

    assert (
        result.operational_context.service
        == "Test Service"
    )

    assert (
        result.operational_context.correlation_id
        == "corr-test-001"
    )


@pytest.mark.asyncio
async def test_procedure_request_executor_rejects_non_eligible_context():
    executor = ProcedureRequestExecutor()
    ctx = FakeWorkflowContext()

    context = create_context(
        procedure_match="exact",
        execution_eligible=False,
        recommended_next_step="knowledge_review",
        procedure_found=True,
    )

    with pytest.raises(
        ValueError,
        match="no cumple los requisitos",
    ):
        await executor.prepare_procedure_request(
            context,
            ctx,
        )

    assert ctx.messages == []
    assert ctx.outputs == []


@pytest.mark.asyncio
async def test_knowledge_review_executor_builds_request():
    executor = KnowledgeReviewExecutor()
    ctx = FakeWorkflowContext()

    context = create_context(
        procedure_match="partial",
        execution_eligible=False,
        recommended_next_step="knowledge_review",
        procedure_found=True,
        missing_context=[
            "Falta confirmar aplicabilidad exacta."
        ],
    )

    await executor.prepare_review(
        context,
        ctx,
    )

    #
    # Knowledge Review es terminal.
    #
    assert ctx.messages == []
    assert len(ctx.outputs) == 1

    result = ctx.outputs[0]

    assert isinstance(
        result,
        KnowledgeReviewRequest,
    )

    assert result.alert_id == "ALT-TEST-001"

    assert (
        result.reason
        == "partial_procedure_match"
    )

    assert result.procedure_id == "PROC-001"

    assert (
        result.procedure_name
        == "Test Procedure"
    )

    assert result.procedure_version == "v1"

    assert (
        result.affected_resource
        == "SERVER01"
    )

    assert result.missing_context == [
        "Falta confirmar aplicabilidad exacta."
    ]


@pytest.mark.asyncio
async def test_knowledge_review_executor_rejects_non_partial():
    executor = KnowledgeReviewExecutor()
    ctx = FakeWorkflowContext()

    context = create_context(
        procedure_match="exact",
        execution_eligible=True,
        recommended_next_step="procedure_execution",
        procedure_found=True,
    )

    with pytest.raises(
        ValueError,
        match="procedure_match=partial",
    ):
        await executor.prepare_review(
            context,
            ctx,
        )

    assert ctx.messages == []
    assert ctx.outputs == []


@pytest.mark.asyncio
async def test_manual_analysis_executor_builds_no_procedure_request():
    executor = ManualAnalysisExecutor()
    ctx = FakeWorkflowContext()

    context = create_context(
        procedure_match="none",
        execution_eligible=False,
        recommended_next_step="manual_analysis",
        procedure_found=False,
        missing_context=[
            "No existe procedimiento corporativo."
        ],
    )

    await executor.prepare_manual_analysis(
        context,
        ctx,
    )

    #
    # Manual Analysis es terminal.
    #
    assert ctx.messages == []
    assert len(ctx.outputs) == 1

    result = ctx.outputs[0]

    assert isinstance(
        result,
        ManualAnalysisRequest,
    )

    assert result.alert_id == "ALT-TEST-001"

    assert result.reason == "no_procedure"

    assert (
        result.technical_domain
        == "database"
    )

    assert (
        result.affected_resource
        == "SERVER01"
    )

    assert result.missing_context == [
        "No existe procedimiento corporativo."
    ]


@pytest.mark.asyncio
async def test_manual_analysis_executor_supports_human_escalation():
    executor = ManualAnalysisExecutor()
    ctx = FakeWorkflowContext()

    context = create_context(
        procedure_match="none",
        execution_eligible=False,
        recommended_next_step="human_escalation",
        procedure_found=False,
    )

    await executor.prepare_manual_analysis(
        context,
        ctx,
    )

    assert ctx.messages == []
    assert len(ctx.outputs) == 1

    result = ctx.outputs[0]

    assert isinstance(
        result,
        ManualAnalysisRequest,
    )

    assert result.alert_id == "ALT-TEST-001"

    assert (
        result.reason
        == "human_escalation_required"
    )

    assert (
        result.technical_domain
        == "database"
    )

    assert (
        result.affected_resource
        == "SERVER01"
    )

    assert result.missing_context == []


@pytest.mark.asyncio
async def test_manual_analysis_executor_rejects_execution_context():
    executor = ManualAnalysisExecutor()
    ctx = FakeWorkflowContext()

    context = create_context(
        procedure_match="exact",
        execution_eligible=True,
        recommended_next_step="procedure_execution",
        procedure_found=True,
    )

    with pytest.raises(
        ValueError,
        match="no corresponde a Manual Analysis",
    ):
        await executor.prepare_manual_analysis(
            context,
            ctx,
        )

    assert ctx.messages == []
    assert ctx.outputs == []