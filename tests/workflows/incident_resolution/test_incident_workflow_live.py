import os
from typing import Any

import pytest

from src.agents.catalog import (
    AgentKey,
)
from src.agents.foundry_agents import (
    FoundryAgents,
)
from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)
from src.workflows.incident_resolution.workflow import (
    build_incident_resolution_workflow,
)


class RecordingFoundryAgents(FoundryAgents):
    """
    Ejecuta los agentes REALES de Microsoft Foundry.

    No hace mocking.

    Solo conserva los resultados tipados para validar
    el recorrido E2E completo.
    """

    def __init__(self) -> None:
        super().__init__()

        self.classification_result: Any | None = None
        self.knowledge_result: Any | None = None
        self.triage_result: Any | None = None
        self.procedure_result: Any | None = None

    async def run_classification(
        self,
        message: str,
    ):
        result = await super().run_classification(
            message
        )

        self.classification_result = result

        return result

    async def run_knowledge(
        self,
        message: str,
    ):
        result = await super().run_knowledge(
            message
        )

        self.knowledge_result = result

        return result

    async def run_alert_triage(
        self,
        message: str,
    ):
        result = await super().run_alert_triage(
            message
        )

        self.triage_result = result

        return result

    async def run_procedure_execution(
        self,
        message: str,
    ):
        result = await super().run_procedure_execution(
            message
        )

        self.procedure_result = result

        return result


def create_live_alert() -> NormalizedAlert:
    """
    Caso LIVE estable y exacto:

    SQL AlwaysOn Role Change
    → NTTSY-PRO-016 v1.1
    """

    return NormalizedAlert(
        alert_id="ALT-SQL-ALWAYSON-ROLE-001",
        source="scom",
        source_event_id=(
            "SCOM-LIVE-ALWAYSON-ROLE-001"
        ),
        name="SQL AlwaysOn Role Change",
        description=(
            "SCOM ha generado una alerta de "
            "cambio de rol de SQL Server Always On "
            "para el Availability Group AG-PROD "
            "en SQLPROD01."
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
        correlation_id=(
            "corr-live-alwayson-role-001"
        ),
        raw_attributes={
            "live_test_marker":
                "must-not-be-used-for-routing"
        },
    )


@pytest.mark.asyncio
@pytest.mark.live
async def test_incident_workflow_live_reaches_hitl():
    """
    E2E LIVE completo:

    NormalizedAlert
        ↓
    Classification v7 REAL
        ↓
    Knowledge v8 REAL
        ↓
    Alert Triage v10 REAL
        ↓
    routing Python
        ↓
    Procedure Execution v5 REAL
        ↓
    ProcedureRuntime REAL
        ↓
    Policy REAL
        ↓
    request_info()
        ↓
    HITL

    No se ejecutan operaciones técnicas.
    """

    if not os.environ.get(
        "FOUNDRY_PROJECT_ENDPOINT"
    ):
        pytest.skip(
            "FOUNDRY_PROJECT_ENDPOINT "
            "no configurado."
        )

    agents = RecordingFoundryAgents()

    #
    # Gate exacto de versiones.
    #
    assert (
        agents.get_definition(
            AgentKey.CLASSIFICATION
        ).version
        == "7"
    )

    assert (
        agents.get_definition(
            AgentKey.KNOWLEDGE
        ).version
        == "8"
    )

    assert (
        agents.get_definition(
            AgentKey.ALERT_TRIAGE
        ).version
        == "10"
    )

    assert (
        agents.get_definition(
            AgentKey.PROCEDURE_EXECUTION
        ).version
        == "6"
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    approval_requests = []

    async for event in workflow.run(
        create_live_alert(),
        stream=True,
    ):
        if event.type == "request_info":
            approval_requests.append(
                event
            )

            break

    #
    # --------------------------------------------------
    # Gates cognitivos
    # --------------------------------------------------
    #

    assert (
        agents.classification_result
        is not None
    )

    assert (
        agents.knowledge_result
        is not None
    )

    assert (
        agents.triage_result
        is not None
    )

    #
    # Triage debe habilitar legítimamente
    # Procedure Execution.
    #
    assert (
        agents.triage_result.procedure_found
        is True
    )

    assert (
        agents.triage_result.procedure_match
        == "exact"
    )

    assert (
        agents.triage_result.execution_eligible
        is True
    )

    assert (
        agents.triage_result.recommended_next_step
        == "procedure_execution"
    )

    assert (
        agents.triage_result.procedure
        is not None
    )

    assert (
        agents.triage_result.procedure.id
        == "NTTSY-PRO-016"
    )

    assert (
        agents.triage_result.procedure.version
        == "v1.1"
    )

    #
    # --------------------------------------------------
    # Procedure Execution REAL
    # --------------------------------------------------
    #

    assert (
        agents.procedure_result
        is not None
    )

    assert (
        agents.procedure_result.alert_id
        == "ALT-SQL-ALWAYSON-ROLE-001"
    )

    assert (
        agents.procedure_result.procedure.id
        == "NTTSY-PRO-016"
    )

    assert (
        agents.procedure_result.procedure.version
        == "v1.1"
    )

    assert (
        agents.procedure_result.execution_allowed
        is True
    )

    assert (
        agents.procedure_result.blocked_by_policy
        is False
    )

    assert (
        agents.procedure_result.current_step
        == 1
    )

    assert (
        agents.procedure_result.step
        is not None
    )

    #
    # --------------------------------------------------
    # HITL
    # --------------------------------------------------
    #

    assert (
        len(approval_requests)
        == 1
    )

    approval_event = (
        approval_requests[0]
    )

    assert (
        approval_event.type
        == "request_info"
    )

    approval = (
        approval_event.data
    )

    #
    # Correlación completa.
    #
    assert (
        approval.alert_id
        == "ALT-SQL-ALWAYSON-ROLE-001"
    )

    assert (
        approval.procedure_id
        == "NTTSY-PRO-016"
    )

    assert (
        approval.current_step
        == 1
    )

    #
    # El procedimiento debe terminar en
    # una operación de lectura/validación
    # antes de cualquier operación técnica.
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
