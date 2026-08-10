import pytest

from src.agents.contracts import (
    ClassificationResult,
)
from src.workflows.incident_resolution.executors.classification import (
    ClassificationExecutor,
)
from src.workflows.incident_resolution.models import (
    NormalizedAlert,
)


class FakeFoundryAgents:
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
                    "Uso elevado de CPU en una máquina virtual Azure.",
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