from datetime import datetime, timezone

import pytest

from src.agents.contracts import (
    ClassificationResult,
)
from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)
from src.workflows.incident_resolution.executors.classification import (
    ClassificationExecutor,
)
from src.workflows.incident_resolution.models import (
    ClassifiedAlertContext,
)


class FakeFoundryAgents:
    """
    Sustituye exclusivamente la llamada real
    a agent-classification-sbx.
    """

    def __init__(self) -> None:
        self.received_message: str | None = None

    async def run_classification(
        self,
        message: str,
    ) -> ClassificationResult:
        self.received_message = message

        return ClassificationResult.model_validate(
            {
                "alert_id": "ALT-CPU-001",
                "alert_classification": "cpu_high",
                "technical_domain": "azure",
                "affected_resource": "vm-demo-01",
                "affected_service":
                    "Microsoft Azure Virtual Machine",
                "classification_summary":
                    "Uso elevado de CPU en una máquina "
                    "virtual Azure.",
                "requires_clarification": False,
                "missing_information": [],
                "confidence": 0.95,
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


def create_alert() -> NormalizedAlert:
    return NormalizedAlert(
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
        subscription_id="sub-test",
        resource_group="rg-test",
        tenant_id="tenant-test",
        correlation_id="corr-001",
        raw_attributes={
            "internal_test_value":
                "must-not-leak"
        },
    )


@pytest.mark.asyncio
async def test_classification_executor_emits_context():
    agents = FakeFoundryAgents()

    executor = ClassificationExecutor(
        agents=agents,
    )

    ctx = FakeWorkflowContext()

    alert = create_alert()

    await executor.classify_alert(
        alert,
        ctx,
    )

    assert len(ctx.messages) == 1

    context = ctx.messages[0]

    assert isinstance(
        context,
        ClassifiedAlertContext,
    )

    assert isinstance(
        context.classification,
        ClassificationResult,
    )

    assert (
        context.alert.alert_id
        == "ALT-CPU-001"
    )

    result = context.classification

    assert result.alert_id == "ALT-CPU-001"

    assert (
        result.alert_classification
        == "cpu_high"
    )

    assert result.technical_domain == "azure"

    assert (
        result.affected_resource
        == "vm-demo-01"
    )

    assert (
        result.requires_clarification
        is False
    )


@pytest.mark.asyncio
async def test_classification_executor_builds_expected_prompt():
    agents = FakeFoundryAgents()

    executor = ClassificationExecutor(
        agents=agents,
    )

    ctx = FakeWorkflowContext()

    await executor.classify_alert(
        create_alert(),
        ctx,
    )

    assert agents.received_message is not None

    prompt = agents.received_message

    assert "ALT-CPU-001" in prompt
    assert "azure_monitor" in prompt
    assert "CPU Percentage High" in prompt
    assert "Sev2" in prompt
    assert "vm-demo-01" in prompt

    assert (
        "Microsoft.Compute/virtualMachines"
        in prompt
    )

    assert (
        "Microsoft Azure Virtual Machine"
        in prompt
    )

    assert "sandbox" in prompt


@pytest.mark.asyncio
async def test_classification_executor_does_not_leak_raw_attributes():
    agents = FakeFoundryAgents()

    executor = ClassificationExecutor(
        agents=agents,
    )

    ctx = FakeWorkflowContext()

    await executor.classify_alert(
        create_alert(),
        ctx,
    )

    assert agents.received_message is not None

    prompt = agents.received_message

    assert "internal_test_value" not in prompt
    assert "must-not-leak" not in prompt


@pytest.mark.asyncio
async def test_classification_executor_preserves_agent_result():
    agents = FakeFoundryAgents()

    executor = ClassificationExecutor(
        agents=agents,
    )

    ctx = FakeWorkflowContext()

    await executor.classify_alert(
        create_alert(),
        ctx,
    )

    context = ctx.messages[0]

    result = context.classification

    assert result.confidence == 0.95

    assert (
        result.classification_summary
        == (
            "Uso elevado de CPU en una máquina "
            "virtual Azure."
        )
    )

    assert result.missing_information == []