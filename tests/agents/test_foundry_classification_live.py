import os

import pytest

from src.agents.contracts import (
    ClassificationResult,
)
from src.agents.foundry_agents import (
    FoundryAgents,
)


@pytest.mark.asyncio
@pytest.mark.live
async def test_foundry_classification_live():
    if not os.environ.get(
        "FOUNDRY_PROJECT_ENDPOINT"
    ):
        pytest.skip(
            "FOUNDRY_PROJECT_ENDPOINT no configurado."
        )

    agents = FoundryAgents()

    prompt = """
Clasifica la siguiente alerta operativa.

Origen: Azure Monitor
AlertId: ALT-CPU-001
Nombre: CPU Percentage High
Severidad origen: Sev2
Recurso: vm-demo-01
Tipo de recurso: Microsoft.Compute/virtualMachines
Descripción: La utilización de CPU ha superado el 90 % durante 15 minutos.

Devuelve únicamente la respuesta estructurada definida por tus instrucciones.
""".strip()

    result = await agents.run_classification(
        prompt
    )

    assert isinstance(
        result,
        ClassificationResult,
    )

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

    assert result.requires_clarification is False

    assert result.missing_information == []

    assert 0.0 <= result.confidence <= 1.0