import os

import pytest

from src.agents.catalog import (
    AgentKey,
)
from src.agents.contracts import (
    AlertTriageResult,
)
from src.agents.foundry_agents import (
    FoundryAgents,
)


@pytest.mark.asyncio
@pytest.mark.live
async def test_foundry_triage_live():
    """
    Valida LIVE agent-alert-triage-sbx v10.

    Caso de baseline:
    SQL AlwaysOn Role Change.

    Este escenario dispone de un procedimiento
    corporativo específicamente identificado:

        NTTSY-PRO-016
        Alertas AlwaysOn_Rol_Change
        v1.1

    El test valida:

    - contrato Pydantic;
    - clasificación técnica;
    - separación entre severidad y criticidad;
    - selección estable del procedimiento principal;
    - procedure_match exact;
    - elegibilidad para Procedure Execution;
    - coherencia de escalado;
    - documentación utilizada;
    - ausencia de falsos prerrequisitos diagnósticos.
    """

    if not os.environ.get(
        "FOUNDRY_PROJECT_ENDPOINT"
    ):
        pytest.skip(
            "FOUNDRY_PROJECT_ENDPOINT "
            "no configurado."
        )

    agents = FoundryAgents()

    #
    # --------------------------------------------------
    # Gate de versión
    # --------------------------------------------------
    #

    definition = agents.get_definition(
        AgentKey.ALERT_TRIAGE
    )

    assert (
        definition.name
        == "agent-alert-triage-sbx"
    )

    assert (
        definition.version
        == "10"
    )

    #
    # --------------------------------------------------
    # Prompt LIVE
    # --------------------------------------------------
    #
    # Utilizamos el escenario estabilizado
    # manualmente para v10.
    #

    prompt = """
Analiza la siguiente alerta:

Origen: SCOM
AlertId: ALT-SQL-ALWAYSON-ROLE-001
Nombre: SQL AlwaysOn Role Change
Severidad origen: Critical
Recurso: SQLPROD01
Tipo de recurso: Microsoft SQL Server Always On Availability Group
Descripción: SCOM ha generado una alerta de cambio de rol de SQL Server Always On para el Availability Group AG-PROD en SQLPROD01.

Clasificación previa:
alert_classification: availability_group_role_change
technical_domain: database
affected_resource: SQLPROD01
affected_service: Microsoft SQL Server Always On Availability Group

Conocimiento corporativo recuperado:

- NTTSY-PRO-016 — Alertas AlwaysOn_Rol_Change v1.1
  Procedimiento específico para el tratamiento de alertas AlwaysOn_Rol_Change. Define como primeras comprobaciones la revisión del estado de sincronización y las comprobaciones diagnósticas correspondientes.

- NTTSY-PRO-031 — Procedimiento Cluster Conmutacion v1.3

- NTTSY-PRO-017 — Revisión de infraestructura de un servidor genérico v1.3

- NTTSY-PRO-020 — Alertas SQL Server v1.1

NTTSY-PRO-016 describe explícitamente este escenario y las comprobaciones necesarias están definidas dentro del propio procedimiento.

Clasifica la alerta utilizando exclusivamente los procedimientos y matrices corporativas disponibles.

Devuelve únicamente la respuesta estructurada definida por tus instrucciones.
""".strip()

    #
    # --------------------------------------------------
    # Invocación REAL
    # --------------------------------------------------
    #

    result = await agents.run_alert_triage(
        prompt
    )

    #
    # --------------------------------------------------
    # Contrato Pydantic
    # --------------------------------------------------
    #

    assert isinstance(
        result,
        AlertTriageResult,
    )

    #
    # --------------------------------------------------
    # Clasificación técnica
    # --------------------------------------------------
    #

    assert (
        result.alert_classification
        == "availability_group_role_change"
    )

    assert (
        result.technical_domain
        == "database"
    )

    assert (
        result.affected_resource
        == "SQLPROD01"
    )

    assert (
        result.affected_service
        == (
            "Microsoft SQL Server Always On "
            "Availability Group"
        )
    )

    #
    # --------------------------------------------------
    # Severidad / criticidad corporativa
    # --------------------------------------------------
    #

    assert (
        result.source_severity
        == "Critical"
    )

    assert (
        result.corporate_criticality
        == "unknown"
    )

    assert (
        result.criticality_source
        == "unknown"
    )

    #
    # --------------------------------------------------
    # Selección estable del procedimiento
    # --------------------------------------------------
    #

    assert (
        result.procedure_found
        is True
    )

    assert (
        result.procedure_match
        == "exact"
    )

    assert (
        result.procedure
        is not None
    )

    assert (
        result.procedure.id
        == "NTTSY-PRO-016"
    )

    assert (
        result.procedure.name
        == "Alertas AlwaysOn_Rol_Change"
    )

    assert (
        result.procedure.version
        == "v1.1"
    )

    #
    # --------------------------------------------------
    # Gate hacia Procedure Execution
    # --------------------------------------------------
    #

    assert (
        result.execution_eligible
        is True
    )

    assert (
        result.knowledge_coverage
        == "complete"
    )

    assert (
        result.recommended_next_step
        == "procedure_execution"
    )

    #
    # --------------------------------------------------
    # Missing context
    # --------------------------------------------------
    #
    # El procedimiento ya define cómo obtener
    # las comprobaciones diagnósticas iniciales.
    #
    # Esos resultados no deben tratarse como
    # prerrequisitos del Triage.
    #

    assert (
        result.missing_context
        == []
    )

    #
    # --------------------------------------------------
    # Escalado
    # --------------------------------------------------
    #

    assert (
        result.escalation.required
        is False
    )

    assert (
        result.escalation.team
        is None
    )

    assert (
        result.escalation.level
        is None
    )

    #
    # Puede existir un criterio documental futuro
    # aunque no esté activado actualmente.
    #

    if (
        result.escalation.criteria
        is not None
    ):
        assert isinstance(
            result.escalation.criteria,
            str,
        )

        assert (
            result.escalation.criteria.strip()
        )

    #
    # La existencia del criterio no debe cambiar
    # la ruta actual a human escalation.
    #

    assert (
        result.recommended_next_step
        != "human_escalation"
    )

    #
    # --------------------------------------------------
    # Falso positivo
    # --------------------------------------------------
    #

    assert (
        result.possible_false_positive
        in {
            "unlikely",
            "possible",
            "likely",
            "unknown",
        }
    )

    #
    # --------------------------------------------------
    # Documentación fuente
    # --------------------------------------------------
    #

    assert (
        len(result.source_documents)
        > 0
    )

    assert any(
        (
            "NTTSY-PRO-016"
            in document
        )
        for document
        in result.source_documents
    )

    #
    # --------------------------------------------------
    # Confianza
    # --------------------------------------------------
    #

    assert (
        0.0
        <= result.confidence
        <= 1.0
    )

    #
    # Existe documentación corporativa suficiente.
    #

    assert (
        result.ai_opinion
        is None
    )