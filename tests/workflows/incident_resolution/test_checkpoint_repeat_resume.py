import pytest

from agent_framework import (
    InMemoryCheckpointStorage,
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

from tests.workflows.incident_resolution.test_phase17_boundary import (
    Phase17BoundaryFakeFoundryAgents,
)


def runtime_from_checkpoint(
    checkpoint,
) -> ProcedureRuntimeState:
    assert (
        "procedure_runtime_state"
        in checkpoint.state
    )

    return (
        ProcedureRuntimeState.model_validate(
            checkpoint.state[
                "procedure_runtime_state"
            ]
        )
    )


@pytest.mark.asyncio
async def test_restore_repeat_checkpoint_is_inert_until_phase17_starts_new_cycle():
    """
    FASE 16.11.6

    REPEAT termina FASE 16 con:

    - step PENDING;
    - workflow RUNNING;
    - approval PENDING;
    - approval_id invalidado;
    - OperationResult invalidado;
    - verification_result invalidado;
    - retry_count incrementado.

    Restaurar ese checkpoint terminal NO puede
    iniciar por sí mismo un nuevo ciclo.

    En particular:

    - no nuevo HITL;
    - no nueva aprobación;
    - no Azure Operations;
    - no Procedure Validation;
    - no output;
    - ningún executor invocado.

    Crear el nuevo intento pertenece a FASE 17.
    """

    storage = (
        InMemoryCheckpointStorage()
    )

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

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    responses = {}

    #
    # ==================================================
    # CICLO 1 — hasta HITL
    # ==================================================
    #

    async for event in workflow.run(
        create_alert(),
        stream=True,
        checkpoint_storage=storage,
    ):
        if (
            event.type
            == "request_info"
        ):
            responses[
                event.request_id
            ] = True

    assert len(
        responses
    ) == 1

    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
    ]

    #
    # ==================================================
    # CICLO 1 — aprobación + operación + REPEAT
    # ==================================================
    #

    outputs = []
    requests_after_approval = []

    async for event in workflow.run(
        responses=responses,
        stream=True,
        checkpoint_storage=storage,
    ):
        if (
            event.type
            == "output"
        ):
            outputs.append(
                event.data
            )

        elif (
            event.type
            == "request_info"
        ):
            requests_after_approval.append(
                event.request_id
            )

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
        requests_after_approval
        == []
    )

    assert len(
        outputs
    ) == 1

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

    assert (
        state.approval_status
        == ApprovalStatus.PENDING
    )

    assert (
        state.approval_id
        is None
    )

    assert (
        state.retry_count
        == 1
    )

    assert (
        state.operation_result
        is None
    )

    assert (
        state.verification_result
        is None
    )

    old_operation_id = (
        agents.validation_operation_id
    )

    assert (
        old_operation_id
        is not None
    )

    #
    # ==================================================
    # LOCALIZAR CHECKPOINT TERMINAL REPEAT
    # ==================================================
    #

    checkpoints = (
        await storage.list_checkpoints(
            workflow_name=workflow.name
        )
    )

    repeat_candidates = []

    for checkpoint in checkpoints:

        if (
            "procedure_runtime_state"
            not in checkpoint.state
        ):
            continue

        checkpoint_state = (
            runtime_from_checkpoint(
                checkpoint
            )
        )

        if (
            checkpoint_state.step_status
            == StepStatus.PENDING
            and checkpoint_state.workflow_status
            == WorkflowStatus.RUNNING
            and checkpoint_state.approval_status
            == ApprovalStatus.PENDING
            and checkpoint_state.approval_id
            is None
            and checkpoint_state.retry_count
            == 1
            and checkpoint_state.operation_result
            is None
            and checkpoint_state.verification_result
            is None
        ):
            repeat_candidates.append(
                checkpoint
            )

    assert len(
        repeat_candidates
    ) == 1

    repeat_checkpoint = (
        repeat_candidates[0]
    )

    checkpoint_state = (
        runtime_from_checkpoint(
            repeat_checkpoint
        )
    )

    #
    # No hay autoridad ni trabajo pendiente
    # escondido en el checkpoint terminal.
    #
    assert (
        checkpoint_state.approval_id
        is None
    )

    assert (
        checkpoint_state.operation_result
        is None
    )

    assert (
        checkpoint_state.verification_result
        is None
    )

    assert (
        repeat_checkpoint.messages
        == {}
    )

    assert (
        repeat_checkpoint
        .pending_request_info_events
        == {}
    )

    #
    # ==================================================
    # RESTART REAL
    # ==================================================
    #

    resumed_agents = (
        Phase17BoundaryFakeFoundryAgents(
            validation_status=(
                "not_satisfied"
            ),
            proposed_next_action=(
                "repeat"
            ),
        )
    )

    resumed_workflow = (
        build_incident_resolution_workflow(
            agents=resumed_agents,
        )
    )

    event_types = []
    resumed_requests = []
    resumed_outputs = []

    async for event in resumed_workflow.run(
        checkpoint_id=(
            repeat_checkpoint
            .checkpoint_id
        ),
        checkpoint_storage=storage,
        stream=True,
    ):
        event_types.append(
            event.type
        )

        if (
            event.type
            == "request_info"
        ):
            resumed_requests.append(
                event.request_id
            )

        elif (
            event.type
            == "output"
        ):
            resumed_outputs.append(
                event.data
            )

    #
    # ==================================================
    # FRONTERA FASE 16 -> FASE 17
    # ==================================================
    #

    assert (
        resumed_agents.calls
        == []
    )

    assert (
        "azure_operations"
        not in resumed_agents.calls
    )

    assert (
        "procedure_validation"
        not in resumed_agents.calls
    )

    assert (
        resumed_requests
        == []
    )

    assert (
        resumed_outputs
        == []
    )

    #
    # El runtime 1.13.0 que hemos probado no
    # invoca ningún executor al restaurar este
    # checkpoint terminal.
    #
    assert (
        "executor_invoked"
        not in event_types
    )

    #
    # El operation_id del intento anterior
    # existió, pero no queda como autoridad
    # operacional dentro del runtime restaurable.
    #
    assert (
        checkpoint_state
        .operation_result
        is None
    )

    assert (
        checkpoint_state
        .approval_id
        is None
    )
