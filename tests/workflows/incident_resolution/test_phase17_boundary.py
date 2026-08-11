import json

import pytest

from src.agents.contracts import (
    ProcedureValidationEscalation,
    ProcedureValidationResult,
)

from src.runtime.procedure.models import (
    ApprovalStatus,
    ProcedureRuntimeState,
    StepStatus,
    WorkflowStatus,
)

from src.workflows.incident_resolution.workflow import (
    build_incident_resolution_workflow,
)

from tests.workflows.incident_resolution.test_incident_workflow import (
    create_alert,
)

from tests.workflows.incident_resolution.test_incident_workflow_azure_operations import (
    AzureWorkflowFakeFoundryAgents,
)


class Phase17BoundaryFakeFoundryAgents(
    AzureWorkflowFakeFoundryAgents
):
    """
    Fake exclusivo de frontera FASE 16 -> FASE 17.

    Permite controlar la propuesta cognitiva de
    Procedure Validation sin modificar:

    - workflow;
    - runtime;
    - HITL;
    - Azure Operations;
    - Transition Gate.
    """

    def __init__(
        self,
        *,
        validation_status: str,
        proposed_next_action: str,
    ) -> None:
        super().__init__()

        self.validation_status = (
            validation_status
        )

        self.proposed_next_action = (
            proposed_next_action
        )

        self.validation_operation_id: (
            str | None
        ) = None

    async def run_procedure_validation(
        self,
        message: str,
    ) -> ProcedureValidationResult:
        self.calls.append(
            "procedure_validation"
        )

        self.procedure_validation_prompt = (
            message
        )

        payload = json.loads(
            message
        )

        operation_id = (
            payload[
                "trusted_identity"
            ][
                "operation_id"
            ]
        )

        self.validation_operation_id = (
            operation_id
        )

        return ProcedureValidationResult(
            operation_id=operation_id,

            validation_status=(
                self.validation_status
            ),

            proposed_next_action=(
                self.proposed_next_action
            ),

            validation_summary=(
                "Resultado controlado para "
                "validar la frontera entre "
                "FASE 16 y FASE 17."
            ),

            escalation=(
                ProcedureValidationEscalation(
                    required=False
                )
            ),
        )


async def run_one_approved_operation_cycle(
    agents,
):
    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    pending_responses = {}

    #
    # Primera ejecución:
    # pipeline pre-operación hasta HITL.
    #
    async for event in workflow.run(
        create_alert(),
        stream=True,
    ):
        if (
            event.type
            == "request_info"
        ):
            pending_responses[
                event.request_id
            ] = True

    assert len(
        pending_responses
    ) == 1

    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
    ]

    #
    # Segunda ejecución:
    # resolver HITL y completar exactamente
    # un ciclo operacional.
    #
    events = []

    async for event in workflow.run(
        responses=pending_responses,
        stream=True,
    ):
        events.append(
            event
        )

    outputs = [
        event.data
        for event in events
        if event.type == "output"
    ]

    new_hitl_requests = [
        event
        for event in events
        if event.type == "request_info"
    ]

    return (
        outputs,
        new_hitl_requests,
    )


def assert_single_operation_cycle(
    agents,
):
    """
    Frontera crítica:

    FASE 16 sólo puede completar un ciclo.

    No puede iniciar por sí misma otro
    prepare_step / HITL / Azure operation.
    """

    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
        "azure_operations",
        "procedure_validation",
    ]

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

    assert (
        agents.calls.count(
            "procedure_validation"
        )
        == 1
    )


@pytest.mark.asyncio
async def test_continue_stops_at_phase17_boundary():
    """
    CONTINUE significa que el step actual ha
    terminado correctamente.

    FASE 16 NO debe preparar ni ejecutar el
    siguiente step.

    Esa continuación pertenece a FASE 17.
    """

    agents = (
        Phase17BoundaryFakeFoundryAgents(
            validation_status="satisfied",
            proposed_next_action="continue",
        )
    )

    (
        outputs,
        new_hitl_requests,
    ) = await run_one_approved_operation_cycle(
        agents
    )

    assert_single_operation_cycle(
        agents
    )

    #
    # FASE 16 no genera el siguiente HITL.
    #
    assert (
        new_hitl_requests
        == []
    )

    assert len(outputs) == 1

    state = outputs[0]

    assert isinstance(
        state,
        ProcedureRuntimeState,
    )

    assert (
        state.step_status
        == StepStatus.SUCCEEDED
    )

    assert (
        state.workflow_status
        == WorkflowStatus.RUNNING
    )

    #
    # FASE 16 todavía no avanza el procedimiento.
    #
    assert (
        state.current_step
        == 1
    )

    #
    # El ciclo que acaba de ejecutarse conserva
    # su autorización y evidencia.
    #
    assert (
        state.approval_id
        is not None
    )

    assert (
        state.operation_result
        is not None
    )

    assert (
        state.verification_result
        is not None
    )

    assert (
        agents.validation_operation_id
        is not None
    )


@pytest.mark.asyncio
async def test_repeat_invalidates_old_cycle_but_does_not_start_new_one():
    """
    REPEAT es especialmente sensible.

    Debe invalidar la autorización y los
    resultados del ciclo anterior.

    Pero FASE 16 NO puede:

    - generar nuevo approval_id;
    - generar nuevo operation_id;
    - lanzar nuevo HITL;
    - ejecutar Azure otra vez.

    Todo eso pertenece a FASE 17.
    """

    agents = (
        Phase17BoundaryFakeFoundryAgents(
            validation_status=(
                "not_satisfied"
            ),
            proposed_next_action=(
                "repeat"
            ),
        )
    )

    (
        outputs,
        new_hitl_requests,
    ) = await run_one_approved_operation_cycle(
        agents
    )

    assert_single_operation_cycle(
        agents
    )

    assert (
        new_hitl_requests
        == []
    )

    assert len(outputs) == 1

    state = outputs[0]

    assert isinstance(
        state,
        ProcedureRuntimeState,
    )

    assert (
        state.step_status
        == StepStatus.PENDING
    )

    assert (
        state.workflow_status
        == WorkflowStatus.RUNNING
    )

    #
    # El mismo step queda preparado para un
    # ciclo futuro, pero no comienza todavía.
    #
    assert (
        state.current_step
        == 1
    )

    assert (
        state.retry_count
        == 1
    )

    #
    # La autorización anterior no puede
    # reutilizarse.
    #
    assert (
        state.approval_id
        is None
    )

    assert (
        state.approval_status
        == ApprovalStatus.PENDING
    )

    assert (
        state.resolved_parameters
        == []
    )

    #
    # El OperationResult y su validación tampoco
    # pueden convertirse en autoridad para el
    # siguiente intento.
    #
    assert (
        state.operation_result
        is None
    )

    assert (
        state.verification_result
        is None
    )

    #
    # Existió un operation_id en el ciclo que
    # acaba de terminar, pero FASE 16 no ha
    # generado otro.
    #
    assert (
        agents.validation_operation_id
        is not None
    )


@pytest.mark.asyncio
async def test_wait_does_not_reexecute_operation():
    """
    WAIT conserva el resultado registrado y su
    validación, pero no inicia ninguna nueva
    operación.

    El desbloqueo/revalidación futura queda fuera
    de la responsabilidad de FASE 16.
    """

    agents = (
        Phase17BoundaryFakeFoundryAgents(
            validation_status=(
                "indeterminate"
            ),
            proposed_next_action=(
                "wait"
            ),
        )
    )

    (
        outputs,
        new_hitl_requests,
    ) = await run_one_approved_operation_cycle(
        agents
    )

    assert_single_operation_cycle(
        agents
    )

    assert (
        new_hitl_requests
        == []
    )

    assert len(outputs) == 1

    state = outputs[0]

    assert isinstance(
        state,
        ProcedureRuntimeState,
    )

    assert (
        state.step_status
        == StepStatus.WAITING_VALIDATION
    )

    assert (
        state.workflow_status
        == WorkflowStatus.WAITING_VALIDATION
    )

    assert (
        state.current_step
        == 1
    )

    assert (
        state.retry_count
        == 0
    )

    assert (
        state.approval_id
        is not None
    )

    assert (
        state.operation_result
        is not None
    )

    assert (
        state.verification_result
        is not None
    )

    assert (
        agents.validation_operation_id
        is not None
    )
