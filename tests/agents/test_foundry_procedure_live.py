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
    if not os.environ.get(
        "FOUNDRY_PROJECT_ENDPOINT"
    ):
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
ID: NTTSY-PRO-016
Nombre: SQL AlwaysOn_Rol Change Alerta
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

    #
    # Contrato Pydantic
    #
    assert isinstance(
        result,
        ProcedureExecutionResult,
    )

    #
    # Correlación con la alerta
    #
    assert result.alert_id == "ALT-SQL-AG-001"

    #
    # Debe mantenerse exactamente el procedimiento
    # seleccionado por Triage.
    #
    assert result.procedure.id == "NTTSY-PRO-016"

    assert (
        result.procedure.name
        == "SQL AlwaysOn_Rol Change Alerta"
    )

    assert result.procedure.version == "v1.1"

    #
    # El procedimiento exacto debe ser procesable.
    #
    assert result.execution_allowed is True

    assert result.blocked_by_policy is False

    #
    # Debe devolver únicamente el primer paso.
    #
    assert result.total_steps > 0

    assert result.current_step == 1

    assert result.step is not None

    assert result.step.id == "1"

    #
    # Para el procedimiento real recuperado,
    # el primer paso es una comprobación de lectura
    # sobre el dominio database.
    #
    assert result.step.operation_domain == "database"

    assert result.step.operation_kind == "read"

    assert (
        result.step.target_resource
        == "SQLPROD01"
    )

    #
    # El paso debe contener una descripción real.
    #
    assert result.step.description

    #
    # No imponemos texto exacto en expected_result
    # ni verification, porque deben proceder
    # exclusivamente del procedimiento recuperado.
    #
    assert result.step.required_parameters is not None

    assert result.step.preconditions is not None

    #
    # El workflow debe continuar hacia la ejecución
    # controlada del paso.
    #
    assert result.next_action == "execute_step"

    #
    # No debe requerir aclaración en este caso.
    #
    assert result.requires_clarification is False

    assert result.missing_information == []

    #
    # Debe existir trazabilidad al documento real
    # recuperado mediante Foundry IQ.
    #
    assert result.source_documents

    assert any(
        "NTTSY-PRO-016" in document
        for document in result.source_documents
    )

    #
    # Confidence siempre dentro del contrato.
    #
    assert 0.0 <= result.confidence <= 1.0