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

from src.workflows.incident_resolution.continuation_context import (
    ProcedureContinuationContext,
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


def _pending_request_ids(
    checkpoint,
):
    pending = (
        checkpoint
        .pending_request_info_events
    )

    if not pending:
        return []

    if isinstance(
        pending,
        dict,
    ):
        return list(
            pending.keys()
        )

    result = []

    for event in pending:
        request_id = getattr(
            event,
            "request_id",
            None,
        )

        if request_id is not None:
            result.append(
                request_id
            )

    return result


def _runtime(
    checkpoint,
):
    return (
        ProcedureRuntimeState
        .model_validate(
            checkpoint.state[
                "procedure_runtime_state"
            ]
        )
    )


def _continuation(
    checkpoint,
):
    return (
        ProcedureContinuationContext
        .model_validate(
            checkpoint.state[
                "procedure_continuation_context"
            ]
        )
    )


async def _reach_second_hitl():
    storage = (
        InMemoryCheckpointStorage()
    )

    agents = (
        Phase17BoundaryFakeFoundryAgents(
            validation_status="satisfied",
            proposed_next_action="continue",
        )
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    first_requests = []

    async for event in workflow.run(
        create_alert(),
        stream=True,
        checkpoint_storage=storage,
    ):
        if (
            event.type
            == "request_info"
        ):
            first_requests.append(
                event.request_id
            )

    assert len(
        first_requests
    ) == 1

    assert (
        agents.requested_steps
        == [1]
    )

    first_request_id = (
        first_requests[0]
    )

    second_requests = []
    outputs = []

    async for event in workflow.run(
        responses={
            first_request_id: True,
        },
        stream=True,
        checkpoint_storage=storage,
    ):
        if (
            event.type
            == "request_info"
        ):
            second_requests.append(
                event.request_id
            )

        elif (
            event.type
            == "output"
        ):
            outputs.append(
                event.data
            )

    assert len(
        second_requests
    ) == 1

    assert outputs == []

    assert (
        agents.requested_steps
        == [1, 2]
    )

    assert (
        agents.calls.count(
            "azure_operations"
        )
        == 1
    )

    checkpoints = (
        await storage
        .list_checkpoints(
            workflow_name=workflow.name
        )
    )

    first_matches = [
        checkpoint
        for checkpoint in checkpoints
        if (
            first_request_id
            in _pending_request_ids(
                checkpoint
            )
        )
    ]

    second_request_id = (
        second_requests[0]
    )

    second_matches = [
        checkpoint
        for checkpoint in checkpoints
        if (
            second_request_id
            in _pending_request_ids(
                checkpoint
            )
        )
    ]

    assert len(
        first_matches
    ) == 1

    assert len(
        second_matches
    ) == 1

    first_hitl = (
        first_matches[0]
    )

    second_hitl = (
        second_matches[0]
    )

    first_runtime = (
        _runtime(
            first_hitl
        )
    )

    second_runtime = (
        _runtime(
            second_hitl
        )
    )

    assert (
        first_runtime.current_step
        == 1
    )

    assert (
        second_runtime.current_step
        == 2
    )

    assert (
        first_runtime.approval_id
        is not None
    )

    assert (
        second_runtime.approval_id
        is not None
    )

    assert (
        first_runtime.approval_id
        != second_runtime.approval_id
    )

    assert (
        second_runtime.workflow_status
        == WorkflowStatus.WAITING_HUMAN
    )

    assert (
        second_runtime.step_status
        == StepStatus.WAITING_APPROVAL
    )

    assert (
        second_runtime.approval_status
        == ApprovalStatus.PENDING
    )

    assert (
        second_runtime.operation_result
        is None
    )

    assert (
        second_runtime.verification_result
        is None
    )

    continuation = (
        _continuation(
            second_hitl
        )
    )

    assert (
        continuation.procedure_found
        is True
    )

    assert (
        continuation.procedure_match
        == "exact"
    )

    assert (
        continuation.execution_eligible
        is True
    )

    return (
        storage,
        first_hitl,
        first_runtime,
        second_hitl,
        second_runtime,
        second_request_id,
    )


@pytest.mark.asyncio
async def test_restore_second_hitl_reemits_same_fresh_approval_without_reexecution():
    (
        storage,
        _,
        first_runtime,
        second_hitl,
        second_runtime,
        second_request_id,
    ) = await _reach_second_hitl()

    resumed_agents = (
        Phase17BoundaryFakeFoundryAgents(
            validation_status="satisfied",
            proposed_next_action="continue",
        )
    )

    resumed_workflow = (
        build_incident_resolution_workflow(
            agents=resumed_agents,
        )
    )

    request_ids = []
    outputs = []

    async for event in resumed_workflow.run(
        checkpoint_id=(
            second_hitl
            .checkpoint_id
        ),
        checkpoint_storage=storage,
        stream=True,
    ):
        if (
            event.type
            == "request_info"
        ):
            request_ids.append(
                event.request_id
            )

        elif (
            event.type
            == "output"
        ):
            outputs.append(
                event.data
            )

    assert request_ids == [
        second_request_id,
    ]

    assert (
        second_runtime.approval_id
        is not None
    )

    assert (
        first_runtime.approval_id
        != second_runtime.approval_id
    )

    assert resumed_agents.calls == []

    assert (
        resumed_agents.requested_steps
        == []
    )

    assert outputs == []


@pytest.mark.asyncio
async def test_restore_and_approve_second_hitl_executes_step_two_once_and_reaches_fresh_step_three_hitl():
    (
        storage,
        _,
        first_runtime,
        second_hitl,
        second_runtime,
        second_request_id,
    ) = await _reach_second_hitl()

    resumed_agents = (
        Phase17BoundaryFakeFoundryAgents(
            validation_status="satisfied",
            proposed_next_action="continue",
        )
    )

    resumed_workflow = (
        build_incident_resolution_workflow(
            agents=resumed_agents,
        )
    )

    third_request_ids = []
    outputs = []

    async for event in resumed_workflow.run(
        checkpoint_id=(
            second_hitl
            .checkpoint_id
        ),
        checkpoint_storage=storage,
        responses={
            second_request_id: True,
        },
        stream=True,
    ):
        if (
            event.type
            == "request_info"
        ):
            third_request_ids.append(
                event.request_id
            )

        elif (
            event.type
            == "output"
        ):
            outputs.append(
                event.data
            )

    #
    # Ningún agente cognitivo previo se reconstruye.
    #
    assert (
        "classification"
        not in resumed_agents.calls
    )

    assert (
        "knowledge"
        not in resumed_agents.calls
    )

    assert (
        "alert_triage"
        not in resumed_agents.calls
    )

    #
    # El step 2 ejecuta exactamente una operación
    # y una validación.
    #
    assert (
        resumed_agents.calls.count(
            "azure_operations"
        )
        == 1
    )

    assert (
        resumed_agents.calls.count(
            "procedure_validation"
        )
        == 1
    )

    #
    # Procedure sólo vuelve a ejecutarse para N+1:
    # step 3.
    #
    assert (
        resumed_agents.calls.count(
            "procedure_execution"
        )
        == 1
    )

    assert (
        resumed_agents.requested_steps
        == [3]
    )

    assert resumed_agents.calls == [
        "azure_operations",
        "procedure_validation",
        "procedure_execution",
    ]

    #
    # CONTINUE del step 2 no es terminal.
    #
    assert outputs == []

    #
    # Debe aparecer un HITL nuevo para step 3.
    #
    assert len(
        third_request_ids
    ) == 1

    third_request_id = (
        third_request_ids[0]
    )

    assert (
        third_request_id
        != second_request_id
    )

    checkpoints = (
        await storage
        .list_checkpoints(
            workflow_name=(
                resumed_workflow.name
            )
        )
    )

    third_matches = [
        checkpoint
        for checkpoint in checkpoints
        if (
            third_request_id
            in _pending_request_ids(
                checkpoint
            )
        )
    ]

    assert len(
        third_matches
    ) == 1

    third_hitl = (
        third_matches[0]
    )

    third_runtime = (
        _runtime(
            third_hitl
        )
    )

    assert (
        third_runtime.current_step
        == 3
    )

    assert (
        third_runtime.total_steps
        == 5
    )

    assert (
        third_runtime.workflow_status
        == WorkflowStatus.WAITING_HUMAN
    )

    assert (
        third_runtime.step_status
        == StepStatus.WAITING_APPROVAL
    )

    assert (
        third_runtime.approval_status
        == ApprovalStatus.PENDING
    )

    assert (
        third_runtime.operation_result
        is None
    )

    assert (
        third_runtime.verification_result
        is None
    )

    #
    # Cada step tiene una autoridad humana distinta.
    #
    assert (
        first_runtime.approval_id
        is not None
    )

    assert (
        second_runtime.approval_id
        is not None
    )

    assert (
        third_runtime.approval_id
        is not None
    )

    assert len(
        {
            first_runtime.approval_id,
            second_runtime.approval_id,
            third_runtime.approval_id,
        }
    ) == 3

    #
    # Agent Framework 1.13.0:
    #
    # respuesta entregada al segundo HITL ->
    # response-entry checkpoint directo,
    # con el mismo iteration_count.
    #
    response_entries = [
        checkpoint
        for checkpoint in checkpoints
        if (
            getattr(
                checkpoint,
                "previous_checkpoint_id",
                None,
            )
            == second_hitl.checkpoint_id
            and getattr(
                checkpoint,
                "iteration_count",
                None,
            )
            == getattr(
                second_hitl,
                "iteration_count",
                None,
            )
        )
    ]

    assert len(
        response_entries
    ) == 1

    response_entry = (
        response_entries[0]
    )

    assert (
        response_entry.checkpoint_id
        != second_hitl.checkpoint_id
    )

    #
    # Continuation context sigue durable también
    # en el tercer HITL.
    #
    third_continuation = (
        _continuation(
            third_hitl
        )
    )

    assert (
        third_continuation.procedure_found
        is True
    )

    assert (
        third_continuation.procedure_match
        == "exact"
    )

    assert (
        third_continuation.execution_eligible
        is True
    )
