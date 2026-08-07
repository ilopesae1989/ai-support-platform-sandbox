import os

import pytest

from src.agents.contracts import (
    ProcedureExecutionResult,
)
from src.agents.foundry_agents import (
    FoundryAgents,
)


@pytest.mark.asyncio
@pytest.mark.live
async def test_foundry_procedure_execution_live():
    if not os.environ.get("FOUNDRY_PROJECT_ENDPOINT"):
        pytest.skip(
            "FOUNDRY_PROJECT_ENDPOINT no configurado."
        )

    agents = FoundryAgents()

    prompt = """
Prepara la ejecución del procedimiento asociado a la siguiente alerta:

AlertId: ALT-SQL-AG-001

Resultado del Triage:
procedure_found: true
procedure_match: exact
execution_eligible: true

Procedimiento:
ID: NTTSY-PRO-020
Nombre: Alertas SQL Server
Versión: v1.1

Recurso afectado:
SQLPROD01

Incidencia:
La réplica secundaria del Availability Group AG-PROD
ha dejado de sincronizarse con la réplica primaria
durante más de 10 minutos.

Recupera el procedimiento corporativo indicado y
devuelve únicamente el primer paso que debe procesarse.
""".strip()

    result = await agents.run_procedure_execution(
        prompt
    )

    assert isinstance(
        result,
        ProcedureExecutionResult,
    )

    assert result.alert_id == "ALT-SQL-AG-001"

    assert result.procedure.id == "NTTSY-PRO-020"

    assert result.procedure.version == "v1.1"

    assert result.execution_allowed is True

    assert result.blocked_by_policy is False

    assert result.current_step == 1

    assert result.step is not None

    assert result.next_action == "execute_step"

    assert len(result.source_documents) > 0