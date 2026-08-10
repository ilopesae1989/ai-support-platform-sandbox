import pytest

from src.agents.contracts import (
    ProcedureExecutionResult,
)

from src.runtime.procedure.workflow import (
    ApprovalOutcome,
)

from src.workflows.incident_resolution.azure_operations_models import (
    AzureOperationResult,
)

from src.workflows.incident_resolution.workflow import (
    build_incident_resolution_workflow,
)

from tests.workflows.incident_resolution.test_incident_workflow import (
    FakeFoundryAgents,
    create_alert,
)


class FakeAzureNativeResponse:
    """
    Respuesta nativa mínima simulada de
    agent-azure-operations-sbx.

    Durante FASE 13/14 todavía no simulamos
    internamente MCP ni tool approval.
    """

    def __init__(
        self,
        text: str,
    ) -> None:
        self.text = text


class AzureWorkflowFakeFoundryAgents(
    FakeFoundryAgents
):
    """
    Fake específico para probar exclusivamente
    la rama Azure del IncidentResolutionWorkflow.

    Este fake NO prueba resolución semántica
    de parámetros.

    Para no mezclar responsabilidades,
    el paso simulado no requiere parámetros
    adicionales.

    Su finalidad continúa siendo probar:

    - wiring;
    - HITL;
    - routing post-HITL;
    - invocación única de Azure Operations.
    """

    def __init__(self) -> None:
        super().__init__()

        self.azure_operations_prompt: (
            str | None
        ) = None

    async def run_procedure_execution(
        self,
        message: str,
        *,
        agent_version: str | None = None,
    ) -> ProcedureExecutionResult:
        self.calls.append(
            "procedure_execution"
        )

        self.procedure_prompt = message

        return (
            ProcedureExecutionResult.model_validate(
                {
                    "alert_id":
                        "ALT-SQL-AG-001",

                    "procedure": {
                        "id":
                            "NTTSY-PRO-016",

                        "name": (
                            "SQL AlwaysOn_Rol "
                            "Change Alerta"
                        ),

                        "version":
                            "v1.1",
                    },

                    "execution_allowed":
                        True,

                    "blocked_by_policy":
                        False,

                    "total_steps":
                        5,

                    "current_step":
                        1,

                    "step": {
                        "id":
                            "1",

                        "description": (
                            "Consultar el estado "
                            "del recurso Azure "
                            "autorizado."
                        ),

                        "step_type":
                            "validation",

                        "operation_domain":
                            "azure",

                        "operation_kind":
                            "read",

                        "target_resource": (
                            "/subscriptions/"
                            "sub-test/"
                            "resourceGroups/"
                            "rg-lab-ia-copilot/"
                            "providers/"
                            "Microsoft.Compute/"
                            "virtualMachines/"
                            "vm-demo-01"
                        ),

                        #
                        # Este test no prueba
                        # parameter resolution.
                        #
                        # Por tanto no inventamos
                        # un pseudo parámetro
                        # "resource=value".
                        #
                        "required_parameters":
                            [],

                        "preconditions":
                            [],

                        "expected_result": (
                            "El estado actual "
                            "del recurso queda "
                            "identificado."
                        ),

                        "verification": (
                            "Validar el resultado "
                            "devuelto por Azure."
                        ),
                    },

                    "resolution_criteria":
                        None,

                    "next_action":
                        "execute_step",

                    "escalation": {
                        "required":
                            False,
                        "team":
                            None,
                        "level":
                            None,
                        "criteria":
                            None,
                    },

                    "requires_clarification":
                        False,

                    "missing_information":
                        [],

                    "source_documents": [
                        (
                            "NTTSY-PRO-016 - "
                            "SQL AlwaysOn_Rol "
                            "Change Alerta v1.1"
                        )
                    ],

                    "confidence":
                        0.95,
                }
            )
        )

    async def run_azure_operations(
        self,
        message: str,
    ):
        """
        Simula:

            agent-azure-operations-sbx v11
                ↓
            Azure MCP

        No existe ninguna llamada real a Foundry.
        """

        self.calls.append(
            "azure_operations"
        )

        self.azure_operations_prompt = (
            message
        )

        return FakeAzureNativeResponse(
            text=(
                "Azure operation fake "
                "completed."
            )
        )


class DatabaseWorkflowFakeFoundryAgents(
    FakeFoundryAgents
):
    """
    Fake database con contador defensivo Azure.

    Si el routing intentase entrar en Azure,
    el test falla inmediatamente.
    """

    def __init__(self) -> None:
        super().__init__()

        self.azure_operations_prompt: (
            str | None
        ) = None

    async def run_azure_operations(
        self,
        message: str,
    ):
        self.calls.append(
            "azure_operations"
        )

        self.azure_operations_prompt = (
            message
        )

        raise AssertionError(
            "La rama Database nunca debe invocar "
            "Azure Operations."
        )


@pytest.mark.asyncio
async def test_approved_azure_step_reaches_azure_operations_once():
    """
    FASE 13.7 / 13.8

    Flujo esperado:

        NormalizedAlert
            ↓
        Classification
            ↓
        Knowledge
            ↓
        Triage
            ↓
        Procedure
            ↓
        Runtime
            ↓
        HITL
            ↓
        approved=True
            ↓
        ApprovedProcedureStep
            ↓
        route_to_azure_operation
            ↓
        AzureOperationsExecutor
            ↓
        run_azure_operations()

    Debe existir exactamente una invocación Azure.
    """

    agents = (
        AzureWorkflowFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    pending_responses = {}

    #
    # Primera ejecución:
    # pipeline hasta HITL.
    #
    async for event in workflow.run(
        create_alert(),
        stream=True,
    ):
        if event.type == "request_info":
            pending_responses[
                event.request_id
            ] = True

    assert len(
        pending_responses
    ) == 1

    #
    # Antes de resolver HITL no puede existir
    # ninguna llamada Azure.
    #
    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
    ]

    #
    # Segunda ejecución:
    # respuesta HITL.
    #
    outputs = []

    async for event in workflow.run(
        responses=pending_responses,
        stream=True,
    ):
        if event.type == "output":
            outputs.append(
                event.data
            )

    #
    # Azure Operations debe haberse invocado
    # exactamente una vez.
    #
    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
        "azure_operations",
    ]

    assert (
        agents.calls.count(
            "azure_operations"
        )
        == 1
    )

    assert len(outputs) == 1

    result = outputs[0]

    assert isinstance(
        result,
        AzureOperationResult,
    )

    assert result.success is True

    assert (
        result.response_text
        == "Azure operation fake completed."
    )

    assert (
        result.workflow_id
        is not None
    )

    assert (
        result.alert_id
        == "ALT-SQL-AG-001"
    )

    assert (
        result.procedure_id
        == "NTTSY-PRO-016"
    )

    assert (
        result.procedure_version
        == "v1.1"
    )

    assert result.current_step == 1

    assert result.step_id == "1"

    assert (
        result.operation_kind.value
        == "read"
    )

    assert (
        result.target_resource
        is not None
    )

    assert (
        result.target_resource.endswith(
            "/virtualMachines/vm-demo-01"
        )
    )

    #
    # Mensaje que atraviesa nuestra frontera
    # hacia Foundry.
    #
    assert (
        agents.azure_operations_prompt
        is not None
    )

    assert (
        "vm-demo-01"
        in agents.azure_operations_prompt
    )

    assert (
        "Tipo: read"
        in agents.azure_operations_prompt
    )


@pytest.mark.asyncio
async def test_rejected_azure_step_never_invokes_azure_operations():
    """
    FASE 13.9

    Una denegación humana debe terminar antes
    de AzureOperationsExecutor.
    """

    agents = (
        AzureWorkflowFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    pending_responses = {}

    async for event in workflow.run(
        create_alert(),
        stream=True,
    ):
        if event.type == "request_info":
            pending_responses[
                event.request_id
            ] = False

    assert len(
        pending_responses
    ) == 1

    outputs = []

    async for event in workflow.run(
        responses=pending_responses,
        stream=True,
    ):
        if event.type == "output":
            outputs.append(
                event.data
            )

    assert (
        "azure_operations"
        not in agents.calls
    )

    assert (
        agents.azure_operations_prompt
        is None
    )

    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
    ]

    assert len(outputs) == 1

    result = outputs[0]

    assert isinstance(
        result,
        ApprovalOutcome,
    )

    assert result.approved is False

    assert result.status == (
        "blocked"
    )


@pytest.mark.asyncio
async def test_database_route_never_invokes_azure_operations():
    """
    FASE 13.10

    Un paso Database aprobado nunca puede
    alcanzar AzureOperationsExecutor.
    """

    agents = (
        DatabaseWorkflowFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    pending_responses = {}

    async for event in workflow.run(
        create_alert(),
        stream=True,
    ):
        if event.type == "request_info":
            pending_responses[
                event.request_id
            ] = True

    assert len(
        pending_responses
    ) == 1

    outputs = []

    async for event in workflow.run(
        responses=pending_responses,
        stream=True,
    ):
        if event.type == "output":
            outputs.append(
                event.data
            )

    assert (
        "azure_operations"
        not in agents.calls
    )

    assert (
        agents.azure_operations_prompt
        is None
    )

    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
    ]

    assert len(outputs) == 1

    result = outputs[0]

    assert (
        getattr(
            result,
            "route",
            None,
        )
        == "database"
    )


@pytest.mark.asyncio
async def test_post_hitl_azure_routing_does_not_reinvoke_cognitive_agents():
    """
    Resolver HITL y alcanzar Azure Operations
    no puede volver a ejecutar:

    - Classification;
    - Knowledge;
    - Alert Triage;
    - Procedure Execution.

    El routing post-HITL continúa siendo Python.
    """

    agents = (
        AzureWorkflowFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    pending_responses = {}

    async for event in workflow.run(
        create_alert(),
        stream=True,
    ):
        if event.type == "request_info":
            pending_responses[
                event.request_id
            ] = True

    assert len(
        pending_responses
    ) == 1

    calls_before_approval = list(
        agents.calls
    )

    assert calls_before_approval == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
    ]

    async for _ in workflow.run(
        responses=pending_responses,
        stream=True,
    ):
        pass

    assert (
        agents.calls.count(
            "classification"
        )
        == 1
    )

    assert (
        agents.calls.count(
            "knowledge"
        )
        == 1
    )

    assert (
        agents.calls.count(
            "alert_triage"
        )
        == 1
    )

    assert (
        agents.calls.count(
            "procedure_execution"
        )
        == 1
    )

    assert (
        agents.calls.count(
            "azure_operations"
        )
        == 1
    )

    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
        "azure_operations",
    ]