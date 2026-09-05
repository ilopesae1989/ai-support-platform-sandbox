import json
import re

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

        self.requested_steps: list[
            int
        ] = []

    async def run_procedure_execution(
        self,
        message: str,
        *,
        agent_version: str | None = None,
    ):
        #
        # El executor productivo entrega al agente
        # el prompt cognitivo, no el envelope.
        #
        # requested_step sigue perteneciendo a
        # Python y se observa aquí únicamente para
        # que el fake histórico respete el contrato.
        #
        matches = re.findall(
            (
                r"^Paso solicitado:"
                r"\s*([0-9]+)\s*$"
            ),
            message,
            flags=(
                re.IGNORECASE
                | re.MULTILINE
            ),
        )

        assert len(matches) == 1

        requested_step = int(
            matches[0]
        )

        self.requested_steps.append(
            requested_step
        )

        result = (
            await super()
            .run_procedure_execution(
                message,
                agent_version=agent_version,
            )
        )

        payload = result.model_dump(
            mode="python"
        )

        #
        # Este fake es deliberadamente multi-step.
        # El fake Azure histórico base es single-step.
        #
        payload[
            "total_steps"
        ] = 5

        payload[
            "current_step"
        ] = requested_step

        step = dict(
            payload[
                "step"
            ]
        )

        step[
            "id"
        ] = str(
            requested_step
        )

        step[
            "description"
        ] = (
            "Historical governed step "
            + str(
                requested_step
            )
            + "."
        )

        payload[
            "step"
        ] = step

        return type(
            result
        ).model_validate(
            payload
        )

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
@pytest.mark.asyncio
async def test_continue_enters_next_step_with_fresh_hitl_boundary():
    """
    CONTINUE ya no es una salida terminal.

    La decisión efectiva de Python debe construir
    exactamente N+1 y volver a Procedure.

    El nuevo paso debe detenerse en un HITL fresco
    antes de cualquier segunda operación.
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

    assert (
        agents.requested_steps
        == [1, 2]
    )

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
        == 2
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

    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
        "azure_operations",
        "procedure_validation",
        "procedure_execution",
    ]

    #
    # CONTINUE no produce output terminal.
    #
    assert outputs == []

    #
    # El paso N+1 requiere una nueva decisión
    # humana antes de ejecutar otra operación.
    #
    assert len(
        new_hitl_requests
    ) == 1

    assert (
        agents.validation_operation_id
        is not None
    )



@pytest.mark.asyncio
async def test_repeat_reenters_same_step_but_does_not_execute_second_operation_before_hitl():
    """
    REPEAT invalida el ciclo anterior y activa
    un nuevo intento del MISMO paso.

    La segunda operación sigue bloqueada por un
    HITL completamente nuevo.
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

    assert (
        agents.requested_steps
        == [1, 1]
    )

    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
        "azure_operations",
        "procedure_validation",
        "procedure_execution",
    ]

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

    assert (
        agents.calls.count(
            "procedure_execution"
        )
        == 2
    )

    assert outputs == []

    assert len(
        new_hitl_requests
    ) == 1

    fresh_request = (
        new_hitl_requests[0]
    )

    assert (
        fresh_request.data.current_step
        == 1
    )

    assert (
        fresh_request.data.approval_id
    )

    assert (
        agents.validation_operation_id
        is not None
    )


@pytest.mark.asyncio
async def test_wait_on_unsupported_legacy_read_fails_closed_without_reexecution():
    """
    El fake histórico de esta frontera representa
    una operación Azure READ legacy.

    FASE 22.8 no puede inventar un mecanismo de
    fresh-read genérico para esa operación.

    Si Procedure Validation propone WAIT sobre una
    operación sin adapter de recheck certificado,
    el workflow debe fallar cerrado después de la
    primera operación y nunca iniciar una segunda.
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

    with pytest.raises(
        ValueError,
        match="azure.vm.start",
    ):
        await run_one_approved_operation_cycle(
            agents
        )

    assert_single_operation_cycle(
        agents
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

    assert (
        agents.validation_operation_id
        is not None
    )


class FinalStepPhase17BoundaryFakeFoundryAgents(
    Phase17BoundaryFakeFoundryAgents
):
    """
    Variante del fake existente cuyo Procedure
    Execution autoritativo representa un único paso.

    No cambia ninguna operación ni invoca servicios.
    """

    async def run_procedure_execution(
        self,
        message: str,
        *,
        agent_version: str | None = None,
    ):
        result = await super().run_procedure_execution(
            message,
            agent_version=agent_version,
        )

        payload = result.model_dump(
            mode="python"
        )

        payload["total_steps"] = 1
        payload["current_step"] = 1

        return type(result).model_validate(
            payload
        )


@pytest.mark.asyncio
async def test_final_step_satisfied_continue_resolves_without_new_cycle():
    """
    En el último paso, CONTINUE no puede dejar el
    workflow RUNNING porque no existe un paso siguiente.

    Python debe cerrar el procedimiento sin:
    - nuevo HITL;
    - nueva operación;
    - nueva llamada cognitiva;
    - avance automático a FASE 17.
    """

    agents = (
        FinalStepPhase17BoundaryFakeFoundryAgents(
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

    assert new_hitl_requests == []

    assert len(outputs) == 1

    state = outputs[0]

    assert isinstance(
        state,
        ProcedureRuntimeState,
    )

    assert state.total_steps == 1
    assert state.current_step == 1

    assert (
        state.step_status
        == StepStatus.SUCCEEDED
    )

    assert (
        state.workflow_status
        == WorkflowStatus.RESOLVED
    )

    assert (
        state.verification_result
        is not None
    )

    assert (
        state.verification_result.success
        is True
    )

    # La operación autorizada y su evidencia
    # siguen siendo el mismo ciclo.
    assert state.approval_id is not None
    assert state.operation_result is not None
