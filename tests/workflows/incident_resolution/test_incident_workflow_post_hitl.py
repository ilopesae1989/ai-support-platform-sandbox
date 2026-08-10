import pytest

from src.runtime.procedure.workflow import (
    ApprovalOutcome,
)
from src.workflows.incident_resolution.executors.post_hitl import (
    PostHitlRouteResult,
)
from src.workflows.incident_resolution.workflow import (
    build_incident_resolution_workflow,
)
from tests.workflows.incident_resolution.test_incident_workflow import (
    FakeFoundryAgents,
    create_alert,
)


@pytest.mark.asyncio
async def test_full_incident_workflow_routes_database_after_approval():
    """
    FASE 12.

    Demuestra el recorrido completo:

    NormalizedAlert
        ↓
    Classification
        ↓
    Knowledge
        ↓
    Alert Triage
        ↓
    routing exact
        ↓
    Procedure Request
        ↓
    Procedure Execution
        ↓
    ProcedureRuntime
        ↓
    HITL
        ↓
    approved=True
        ↓
    ApprovedProcedureStep
        ↓
    routing determinista post-HITL
        ↓
    DatabaseRouteExecutor
        ↓
    PostHitlRouteResult(route="database")

    No se ejecuta ninguna operación técnica.
    """

    agents = FakeFoundryAgents()

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    alert = create_alert()

    #
    # --------------------------------------------------
    # Primera ejecución:
    # NormalizedAlert -> HITL
    # --------------------------------------------------
    #

    pending_responses = {}

    async for event in workflow.run(
        alert,
        stream=True,
    ):
        if event.type == "request_info":
            pending_responses[
                event.request_id
            ] = True

    #
    # Los cuatro Prompt Agents deben haberse
    # ejecutado exactamente una vez y en orden.
    #

    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
    ]

    #
    # Debe existir exactamente una solicitud HITL.
    #

    assert len(pending_responses) == 1

    #
    # --------------------------------------------------
    # Segunda ejecución:
    # aprobación HITL -> routing post-HITL
    # --------------------------------------------------
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
    # Debe alcanzarse exactamente
    # un destino terminal.
    #

    assert len(outputs) == 1

    result = outputs[0]

    #
    # Debe ser el contrato temporal
    # de routing de FASE 12.
    #

    assert isinstance(
        result,
        PostHitlRouteResult,
    )

    #
    # --------------------------------------------------
    # Routing
    # --------------------------------------------------
    #
    # Procedure fake devuelve:
    #
    # operation_domain = database
    # operation_kind = read
    #
    # ApprovedProcedureStep fija:
    #
    # next_action = execute_step
    #
    # Por tanto el único destino válido
    # es DatabaseRouteExecutor.
    #

    assert (
        result.route
        == "database"
    )

    #
    # --------------------------------------------------
    # Correlación
    # --------------------------------------------------
    #

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

    assert (
        result.current_step
        == 1
    )

    assert (
        result.step_id
        == "1"
    )

    #
    # --------------------------------------------------
    # Operación aprobada
    # --------------------------------------------------
    #

    assert (
        result.operation_kind
        == "read"
    )

    assert (
        result.target_resource
        == "SQLPROD01"
    )

    #
    # Una ruta válida no debe contener
    # motivo de bloqueo.
    #

    assert (
        result.blocked_reason
        is None
    )


@pytest.mark.asyncio
async def test_full_incident_workflow_rejection_never_reaches_operational_routing():
    """
    Garantía fail-closed.

    Una denegación humana termina el workflow
    ANTES del routing operativo post-HITL.

    Flujo esperado:

        request_info
            ↓
        approved=False
            ↓
        ApprovalOutcome
            ↓
        FIN

    No debe generarse ApprovedProcedureStep.

    No debe alcanzarse:

    - DatabaseRouteExecutor;
    - AzureRouteExecutor;
    - ITSM;
    - Windows;
    - Linux;
    - Networking;
    - Microsoft 365;
    - BlockedRouteExecutor.

    El rechazo humano no es una ruta operativa:
    es una terminación explícita del HITL.
    """

    agents = FakeFoundryAgents()

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

    #
    # Debe existir exactamente una solicitud HITL.
    #

    assert len(pending_responses) == 1

    #
    # Respondemos con rechazo.
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
    # El rechazo debe producir una única
    # salida terminal.
    #

    assert len(outputs) == 1

    result = outputs[0]

    #
    # Muy importante:
    #
    # NO debe ser PostHitlRouteResult.
    #
    # El rechazo nunca ha entrado al router.
    #

    assert isinstance(
        result,
        ApprovalOutcome,
    )

    assert (
        result.approved
        is False
    )

    assert (
        result.workflow_id
        is not None
    )

    assert (
        result.status
        == "blocked"
    )

    #
    # Tampoco se permite una nueva llamada
    # cognitiva después del rechazo.
    #

    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
    ]


@pytest.mark.asyncio
async def test_full_incident_workflow_post_hitl_does_not_reinvoke_llms():
    """
    Verifica la separación LLM / determinismo.

    El routing post-HITL debe ser exclusivamente
    Python / Agent Framework.

    Resolver la aprobación NO puede provocar
    nuevas llamadas a:

    - Classification;
    - Knowledge;
    - Alert Triage;
    - Procedure Execution.

    Ningún LLM decide el dominio operativo.
    """

    agents = FakeFoundryAgents()

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    pending_responses = {}

    #
    # --------------------------------------------------
    # Ejecutamos hasta HITL.
    # --------------------------------------------------
    #

    async for event in workflow.run(
        create_alert(),
        stream=True,
    ):
        if event.type == "request_info":
            pending_responses[
                event.request_id
            ] = True

    assert len(pending_responses) == 1

    calls_before_approval = list(
        agents.calls
    )

    assert calls_before_approval == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
    ]

    #
    # --------------------------------------------------
    # Respondemos al HITL.
    # --------------------------------------------------
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
    # --------------------------------------------------
    # No puede haberse reinvocado ningún LLM.
    # --------------------------------------------------
    #

    assert (
        agents.calls
        == calls_before_approval
    )

    #
    # Debe existir una única salida operativa.
    #

    assert len(outputs) == 1

    result = outputs[0]

    assert isinstance(
        result,
        PostHitlRouteResult,
    )

    assert (
        result.route
        == "database"
    )

    assert (
        result.operation_kind
        == "read"
    )

    assert (
        result.target_resource
        == "SQLPROD01"
    )


@pytest.mark.asyncio
async def test_full_incident_workflow_preserves_approved_operation_identity():
    """
    Garantía de integridad de la operación
    entre Procedure Execution, HITL y routing.

    El routing post-HITL no puede cambiar:

    - alerta;
    - procedimiento;
    - versión;
    - paso;
    - operation_kind;
    - target_resource.

    Esta prueba prepara la base para FASE 14,
    donde la verificación pre-call será todavía
    más estricta.
    """

    agents = FakeFoundryAgents()

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    approval_request = None
    pending_responses = {}

    #
    # --------------------------------------------------
    # Pipeline hasta HITL.
    # --------------------------------------------------
    #

    async for event in workflow.run(
        create_alert(),
        stream=True,
    ):
        if event.type == "request_info":
            approval_request = event.data

            pending_responses[
                event.request_id
            ] = True

    assert approval_request is not None

    assert len(pending_responses) == 1

    #
    # Valores que el humano ha visto.
    #

    assert (
        approval_request.alert_id
        == "ALT-SQL-AG-001"
    )

    assert (
        approval_request.procedure_id
        == "NTTSY-PRO-016"
    )

    assert (
        approval_request.current_step
        == 1
    )

    assert (
        approval_request.operation_domain
        == "database"
    )

    assert (
        approval_request.operation_kind
        == "read"
    )

    assert (
        approval_request.target_resource
        == "SQLPROD01"
    )

    #
    # --------------------------------------------------
    # Aprobamos.
    # --------------------------------------------------
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

    assert len(outputs) == 1

    result = outputs[0]

    assert isinstance(
        result,
        PostHitlRouteResult,
    )

    #
    # --------------------------------------------------
    # Lo aprobado debe llegar intacto.
    # --------------------------------------------------
    #

    assert (
        result.alert_id
        == approval_request.alert_id
    )

    assert (
        result.procedure_id
        == approval_request.procedure_id
    )

    assert (
        result.current_step
        == approval_request.current_step
    )

    assert (
        result.route
        == approval_request.operation_domain
    )

    assert (
        result.operation_kind
        == approval_request.operation_kind
    )

    assert (
        result.target_resource
        == approval_request.target_resource
    )