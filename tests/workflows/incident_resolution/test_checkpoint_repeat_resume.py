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
async def test_restore_repeat_fresh_hitl_checkpoint_reemits_request_without_operation():
    """
    REPEAT activo termina el primer intento y
    crea un segundo HITL para el MISMO step.

    Restaurar el checkpoint del segundo HITL:
    - reemite la request pendiente;
    - no ejecuta Azure;
    - no ejecuta Procedure Validation;
    - no llama otra vez a Procedure Execution.

    Sólo responder afirmativamente al HITL
    puede iniciar la segunda operación.
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

    first_requests = []
    first_responses = {}

    async for event in workflow.run(
        create_alert(),
        stream=True,
        checkpoint_storage=storage,
    ):
        if event.type == "request_info":
            first_requests.append(
                event
            )

            first_responses[
                event.request_id
            ] = True

    assert len(first_requests) == 1

    first_approval_id = (
        first_requests[0]
        .data
        .approval_id
    )

    assert first_approval_id

    second_requests = []
    outputs = []

    async for event in workflow.run(
        responses=first_responses,
        stream=True,
        checkpoint_storage=storage,
    ):
        if event.type == "request_info":
            second_requests.append(
                event
            )

        elif event.type == "output":
            outputs.append(
                event.data
            )

    assert outputs == []

    assert (
        agents.requested_steps
        == [1, 1]
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

    assert len(second_requests) == 1

    second_request = (
        second_requests[0]
    )

    second_approval_id = (
        second_request
        .data
        .approval_id
    )

    assert second_approval_id
    assert (
        second_approval_id
        != first_approval_id
    )

    assert (
        second_request
        .data
        .current_step
        == 1
    )

    first_operation_id = (
        agents.validation_operation_id
    )

    assert first_operation_id

    checkpoints = (
        await storage.list_checkpoints(
            workflow_name=workflow.name
        )
    )

    candidates = []

    for checkpoint in checkpoints:
        if (
            second_request.request_id
            not in checkpoint
            .pending_request_info_events
        ):
            continue

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
            checkpoint_state.current_step == 1
            and checkpoint_state.retry_count == 1
            and checkpoint_state.step_status
            == StepStatus.WAITING_APPROVAL
            and checkpoint_state.workflow_status
            == WorkflowStatus.WAITING_HUMAN
            and checkpoint_state.approval_status
            == ApprovalStatus.PENDING
            and checkpoint_state.approval_id
            == second_approval_id
            and checkpoint_state.operation_result
            is None
            and checkpoint_state.verification_result
            is None
        ):
            candidates.append(
                checkpoint
            )

    assert len(candidates) == 1

    second_hitl_checkpoint = (
        candidates[0]
    )

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

    restored_requests = []
    restored_outputs = []

    async for event in resumed_workflow.run(
        checkpoint_id=(
            second_hitl_checkpoint
            .checkpoint_id
        ),
        checkpoint_storage=storage,
        stream=True,
    ):
        if event.type == "request_info":
            restored_requests.append(
                event
            )

        elif event.type == "output":
            restored_outputs.append(
                event.data
            )

    assert resumed_agents.calls == []
    assert restored_outputs == []

    assert len(
        restored_requests
    ) == 1

    assert (
        restored_requests[0]
        .request_id
        == second_request.request_id
    )

    assert (
        restored_requests[0]
        .data
        .approval_id
        == second_approval_id
    )

    third_requests = []
    response_outputs = []

    async for event in resumed_workflow.run(
        responses={
            second_request.request_id:
                True
        },
        checkpoint_storage=storage,
        stream=True,
    ):
        if event.type == "request_info":
            third_requests.append(
                event
            )

        elif event.type == "output":
            response_outputs.append(
                event.data
            )

    assert response_outputs == []

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

    assert (
        resumed_agents.calls.count(
            "procedure_execution"
        )
        == 1
    )

    assert resumed_agents.calls == [
        "azure_operations",
        "procedure_validation",
        "procedure_execution",
    ]

    assert len(third_requests) == 1

    third_request = (
        third_requests[0]
    )

    assert (
        third_request.data.current_step
        == 1
    )

    assert (
        third_request.data.approval_id
        != second_approval_id
    )

    second_operation_id = (
        resumed_agents
        .validation_operation_id
    )

    assert second_operation_id
    assert (
        second_operation_id
        != first_operation_id
    )
