import os

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
    Adaptador LIVE de diagnóstico.

    Utiliza los Prompt Agents reales de Foundry,
    pero conserva sus respuestas estructuradas para
    poder inspeccionar qué ha decidido realmente
    cada etapa del pipeline.

    NO sustituye respuestas.
    NO modifica resultados.
    NO fuerza routing.
    """

    def __init__(self) -> None:
        super().__init__()

        self.classification_result = None
        self.knowledge_result = None
        self.triage_result = None
        self.procedure_result = None

        self.azure_operations_calls = 0

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
        result = (
            await super().run_procedure_execution(
                message
            )
        )

        self.procedure_result = result

        return result

    async def run_azure_operations(
        self,
        message: str,
    ):
        """
        Guardia de seguridad de esta sonda.

        Este test NO debe alcanzar Azure Operations.

        Si por cualquier motivo intentara hacerlo,
        abortamos inmediatamente.
        """

        self.azure_operations_calls += 1

        raise AssertionError(
            "La sonda cognitiva LIVE no debe "
            "ejecutar Azure Operations."
        )


def create_live_azure_alert() -> NormalizedAlert:
    """
    Caso LIVE real de la sandbox.

    Solicitud de inventario exclusivamente de lectura
    sobre una suscripción Azure autorizada.

    El input NO indica:

    - procedure_id;
    - procedure_match;
    - execution_eligible;
    - operation_domain;
    - operation_kind;
    - next_action.

    Esos datos deben ser descubiertos o decididos por:

    - Classification;
    - Knowledge + Foundry IQ;
    - Triage;
    - Procedure;
    - routing determinista Python.

    El objetivo es comprobar si el procedimiento
    corporativo NTTSY-SBX-AZ-001 es recuperado
    naturalmente por el pipeline, sin forzar el
    resultado esperado desde el test.
    """

    return NormalizedAlert(
        alert_id="ALT-AZ-RG-LIST-001",
        source="azure_monitor",
        source_event_id=(
            "AZMON-RG-LIST-001"
        ),
        name=(
            "Azure Subscription Resource Groups "
            "Inventory Request"
        ),
        description=(
            "Se requiere obtener el listado de "
            "Resource Groups existentes en la "
            "suscripción Azure "
            "557fdabc-f3b6-4c24-"
            "a9ae-e9e89b5ad172. "
            "La consulta debe ser exclusivamente "
            "de lectura y limitarse a esta "
            "suscripción."
        ),
        source_severity="Sev2",
        affected_resource=(
            "557fdabc-f3b6-4c24-"
            "a9ae-e9e89b5ad172"
        ),
        resource_type=(
            "subscription"
        ),
        service=(
            "Azure Resource Manager"
        ),
        environment="sandbox",
        subscription_id=(
            "557fdabc-f3b6-4c24-"
            "a9ae-e9e89b5ad172"
        ),
        resource_group=None,
        tenant_id=(
            "0cb40b2b-6cfc-4c63-"
            "bf7b-da710ea390cb"
        ),
        correlation_id=(
            "corr-azure-rg-list-live-001"
        ),
        raw_attributes={
            "probe": True,
            "operation": "read_only",
        },
    )


@pytest.mark.asyncio
@pytest.mark.live
async def test_incident_workflow_azure_live_probe():
    """
    FASE 13.12 — sonda cognitiva previa.

    Pipeline REAL:

        NormalizedAlert
            ↓
        Classification real
            ↓
        Knowledge real
            ↓
        Foundry IQ
            ↓
        Triage real
            ↓
        routing Python
            ↓
        Procedure real, SI corresponde
            ↓
        Runtime
            ↓
        HITL, SI corresponde

    Este test termina sin responder a HITL.

    Por tanto:

    - no hay aprobación;
    - no hay ApprovedProcedureStep operativo;
    - no hay AzureOperationsExecutor;
    - no hay llamada Azure MCP.

    El caso esperado actualmente es:

        solicitud Resource Groups
            ↓
        Knowledge recupera NTTSY-SBX-AZ-001
            ↓
        Triage:
            procedure_match = exact
            execution_eligible = True
            ↓
        Procedure:
            operation_domain = azure
            operation_kind = read
            next_action = execute_step
            ↓
        Runtime
            ↓
        HITL

    IMPORTANTE:

    Este test NO fuerza que ese sea el resultado.

    Si Knowledge no encuentra el procedimiento,
    Triage decide partial/none o Procedure no
    permite ejecución, el workflow debe mantener
    su comportamiento fail-closed.

    El objetivo es observar qué produce realmente
    el pipeline LIVE para este escenario.
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
    # --------------------------------------------------
    # Gate de baseline
    # --------------------------------------------------
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

    assert (
        agents.get_definition(
            AgentKey.AZURE_OPERATIONS
        ).version
        == "11"
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    request_info_events = []
    output_events = []

    #
    # --------------------------------------------------
    # Ejecución LIVE
    # --------------------------------------------------
    #

    async for event in workflow.run(
        create_live_azure_alert(),
        stream=True,
    ):
        if event.type == "request_info":
            request_info_events.append(
                event
            )

            #
            # NO respondemos.
            #
            # El probe termina aquí si llega a HITL.
            #
            continue

        if event.type == "output":
            output_events.append(
                event
            )

    #
    # --------------------------------------------------
    # Diagnóstico
    # --------------------------------------------------
    #

    print()
    print("=" * 80)
    print(
        "AZURE INCIDENT WORKFLOW LIVE PROBE"
    )
    print("=" * 80)

    print()
    print("# CLASSIFICATION")
    print()

    print(
        agents.classification_result
    )

    print()
    print("# KNOWLEDGE")
    print()

    print(
        agents.knowledge_result
    )

    print()
    print("# TRIAGE")
    print()

    print(
        agents.triage_result
    )

    print()
    print("# PROCEDURE")
    print()

    print(
        agents.procedure_result
    )

    print()
    print("# ROUTE DIAGNOSTIC")
    print()

    if agents.triage_result is not None:
        print(
            "procedure_found =",
            agents.triage_result.procedure_found,
        )

        print(
            "procedure_match =",
            agents.triage_result.procedure_match,
        )

        print(
            "execution_eligible =",
            agents.triage_result.execution_eligible,
        )

        print(
            "recommended_next_step =",
            (
                agents.triage_result
                .recommended_next_step
            ),
        )

        print(
            "technical_domain =",
            agents.triage_result.technical_domain,
        )

        print(
            "missing_context =",
            agents.triage_result.missing_context,
        )

    if agents.procedure_result is not None:
        print()
        print("# PROCEDURE STEP")

        print(
            "operation_domain =",
            (
                agents.procedure_result
                .step.operation_domain
            ),
        )

        print(
            "operation_kind =",
            (
                agents.procedure_result
                .step.operation_kind
            ),
        )

        print(
            "next_action =",
            agents.procedure_result.next_action,
        )

        print(
            "target_resource =",
            (
                agents.procedure_result
                .step.target_resource
            ),
        )

        print(
            "required_parameters =",
            (
                agents.procedure_result
                .step.required_parameters
            ),
        )

    print()
    print(
        "request_info_count =",
        len(request_info_events),
    )

    print(
        "output_count =",
        len(output_events),
    )

    print(
        "azure_operations_calls =",
        agents.azure_operations_calls,
    )

    #
    # --------------------------------------------------
    # Invariantes de seguridad
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
    # La sonda nunca puede alcanzar Azure Operations.
    #
    assert (
        agents.azure_operations_calls
        == 0
    )

    #
    # No exigimos aquí que Procedure exista.
    #
    # Eso es precisamente lo que estamos
    # descubriendo con el LIVE.
    #