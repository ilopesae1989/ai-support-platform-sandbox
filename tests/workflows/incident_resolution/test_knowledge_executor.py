from datetime import datetime, timezone

import pytest

from src.agents.contracts import (
    ClassificationResult,
    KnowledgeResult,
)
from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)
from src.workflows.incident_resolution.executors.knowledge import (
    KnowledgeExecutor,
)
from src.workflows.incident_resolution.models import (
    ClassifiedAlertContext,
    KnowledgeEnrichedAlertContext,
)


class FakeFoundryAgents:
    """
    Sustituye exclusivamente la llamada real
    a agent-knowledge-sbx.
    """

    def __init__(self) -> None:
        self.received_message: str | None = None

    async def run_knowledge(
        self,
        message: str,
    ) -> KnowledgeResult:
        self.received_message = message

        return KnowledgeResult.model_validate(
            {
                "alert_id": "ALT-CPU-001",
                "knowledge_found": True,
                "documents": [
                    {
                        "id": "NTTSY-PRO-017",
                        "name": (
                            "Revisión de infraestructura "
                            "de un servidor genérico"
                        ),
                        "version": "v1.3",
                        "relevance_summary": (
                            "Contiene revisión de CPU "
                            "y métricas de servidor."
                        ),
                    }
                ],
                "knowledge_summary": (
                    "La documentación recuperada contiene "
                    "información relacionada con CPU."
                ),
                "limitations": [
                    (
                        "No existe un procedimiento específico "
                        "para la VM indicada."
                    )
                ],
                "confidence": 0.88,
            }
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


def create_context() -> ClassifiedAlertContext:
    alert = NormalizedAlert(
        alert_id="ALT-CPU-001",
        source="azure_monitor",
        source_event_id="AM-0001",
        name="CPU Percentage High",
        description=(
            "La utilización de CPU ha superado "
            "el 90 % durante 15 minutos."
        ),
        source_severity="Sev2",
        timestamp=datetime(
            2026,
            8,
            8,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        affected_resource="vm-demo-01",
        resource_type=(
            "Microsoft.Compute/virtualMachines"
        ),
        service="Microsoft Azure Virtual Machine",
        environment="sandbox",
        raw_attributes={
            "secret_native_payload":
                "must-not-leak"
        },
    )

    classification = ClassificationResult.model_validate(
        {
            "alert_id": "ALT-CPU-001",
            "alert_classification": "cpu_high",
            "technical_domain": "azure",
            "affected_resource": "vm-demo-01",
            "affected_service":
                "Microsoft Azure Virtual Machine",
            "classification_summary":
                "Uso elevado de CPU.",
            "requires_clarification": False,
            "missing_information": [],
            "confidence": 0.95,
        }
    )

    return ClassifiedAlertContext(
        alert=alert,
        classification=classification,
    )


@pytest.mark.asyncio
async def test_knowledge_executor_emits_enriched_context():
    agents = FakeFoundryAgents()

    executor = KnowledgeExecutor(
        agents=agents,
    )

    ctx = FakeWorkflowContext()

    context = create_context()

    await executor.retrieve_knowledge(
        context,
        ctx,
    )

    assert len(ctx.messages) == 1

    result = ctx.messages[0]

    assert isinstance(
        result,
        KnowledgeEnrichedAlertContext,
    )

    assert (
        result.alert.alert_id
        == "ALT-CPU-001"
    )

    assert (
        result.classification.alert_classification
        == "cpu_high"
    )

    assert result.knowledge.knowledge_found is True

    assert (
        result.knowledge.documents[0].id
        == "NTTSY-PRO-017"
    )


@pytest.mark.asyncio
async def test_knowledge_executor_builds_expected_prompt():
    agents = FakeFoundryAgents()

    executor = KnowledgeExecutor(
        agents=agents,
    )

    ctx = FakeWorkflowContext()

    await executor.retrieve_knowledge(
        create_context(),
        ctx,
    )

    assert agents.received_message is not None

    prompt = agents.received_message

    assert "ALT-CPU-001" in prompt
    assert "cpu_high" in prompt
    assert "azure" in prompt
    assert "vm-demo-01" in prompt

    assert (
        "Microsoft.Compute/virtualMachines"
        in prompt
    )

    assert (
        "Microsoft Azure Virtual Machine"
        in prompt
    )


@pytest.mark.asyncio
async def test_knowledge_executor_does_not_leak_raw_attributes():
    agents = FakeFoundryAgents()

    executor = KnowledgeExecutor(
        agents=agents,
    )

    ctx = FakeWorkflowContext()

    await executor.retrieve_knowledge(
        create_context(),
        ctx,
    )

    assert agents.received_message is not None

    prompt = agents.received_message

    assert "secret_native_payload" not in prompt
    assert "must-not-leak" not in prompt


@pytest.mark.asyncio
async def test_knowledge_executor_preserves_previous_context():
    agents = FakeFoundryAgents()

    executor = KnowledgeExecutor(
        agents=agents,
    )

    ctx = FakeWorkflowContext()

    original = create_context()

    await executor.retrieve_knowledge(
        original,
        ctx,
    )

    enriched = ctx.messages[0]

    assert enriched.alert == original.alert

    assert (
        enriched.classification
        == original.classification
    )

    assert enriched.knowledge.confidence == 0.88