import importlib

import pytest

from agent_framework import (
    InMemoryCheckpointStorage,
)

from src.runtime.procedure.models import (
    ApprovalStatus,
    NextAction,
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

from tests.workflows.incident_resolution.test_procedure_continuation_request_builder import (
    make_continuation_context,
    make_outcome,
    make_runtime_state,
)


BUILDER_MODULE = (
    "src.workflows.incident_resolution."
    "continuation_request_builder"
)


def load_repeat_builder():
    module = importlib.import_module(
        BUILDER_MODULE
    )

    builder = getattr(
        module,
        "build_procedure_repeat_input",
        None,
    )

    assert callable(
        builder
    ), (
        "Falta build_procedure_repeat_input: "
        "REPEAT no dispone todavía de un builder "
        "Python-owned para same-step continuation."
    )

    return builder


def make_repeat_outcome(
    *,
    total_steps=5,
    current_step=1,
    retry_count=1,
):
    state = make_runtime_state()

    state.total_steps = total_steps
    state.current_step = current_step
    state.retry_count = retry_count

    state.approval_id = None
    state.approval_status = (
        ApprovalStatus.PENDING
    )

    state.resolved_parameters = []
    state.operation_result = None
    state.verification_result = None

    state.escalation_required = False
    state.escalation_team = None
    state.escalation_level = None
    state.escalation_criteria = None

    state.step_status = (
        StepStatus.PENDING
    )

    state.workflow_status = (
        WorkflowStatus.RUNNING
    )

    return make_outcome(
        state=state,
        next_action=NextAction.REPEAT,
    )


def test_repeat_builder_constructs_exact_same_step_request():
    builder = load_repeat_builder()

    outcome = make_repeat_outcome(
        total_steps=5,
        current_step=3,
        retry_count=1,
    )

    result = builder(
        outcome=outcome,
        continuation=(
            make_continuation_context()
        ),
    )

    assert result.request.requested_step == 3

    assert (
        result.request.requested_step
        == outcome.state.current_step
    )

    assert (
        result.execution_identity.workflow_id
        == outcome.state.workflow_id
    )

    assert (
        result.execution_identity.alert_id
        == outcome.state.alert_id
    )

    assert (
        result.execution_identity.correlation_id
        == outcome.state.correlation_id
    )


def test_repeat_builder_rejects_exhausted_certified_attempt_budget():
    builder = load_repeat_builder()

    outcome = make_repeat_outcome(
        total_steps=8,
        current_step=1,
        retry_count=1,
    )

    assert (
        outcome.state.total_steps
        + outcome.state.retry_count
        == 9
    )

    with pytest.raises(
        ValueError,
        match=r"(?i)(iteration|attempt|budget)",
    ):
        builder(
            outcome=outcome,
            continuation=(
                make_continuation_context()
            ),
        )


@pytest.mark.asyncio
async def test_repeat_reenters_same_step_with_fresh_hitl_and_preserves_retry_count():
    storage = InMemoryCheckpointStorage()

    agents = (
        Phase17BoundaryFakeFoundryAgents(
            validation_status="not_satisfied",
            proposed_next_action="repeat",
        )
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    first_requests = []
    responses = {}

    async for event in workflow.run(
        create_alert(),
        stream=True,
        checkpoint_storage=storage,
    ):
        if event.type == "request_info":
            first_requests.append(event)
            responses[event.request_id] = True

    assert len(first_requests) == 1

    first_request = first_requests[0]
    first_approval_id = first_request.data.approval_id

    assert first_approval_id

    events = []

    async for event in workflow.run(
        responses=responses,
        stream=True,
        checkpoint_storage=storage,
    ):
        events.append(event)

    outputs = [
        event.data
        for event in events
        if event.type == "output"
    ]

    second_requests = [
        event
        for event in events
        if event.type == "request_info"
    ]

    assert agents.requested_steps == [1, 1]

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

    assert outputs == []

    assert len(second_requests) == 1

    second_request = second_requests[0]
    second_approval_id = second_request.data.approval_id

    assert second_approval_id
    assert second_approval_id != first_approval_id
    assert second_request.data.current_step == 1

    assert (
        second_request.data.next_action
        == NextAction.EXECUTE_STEP.value
    )

    checkpoints = await storage.list_checkpoints(
        workflow_name=workflow.name
    )

    matching_states = []

    for checkpoint in checkpoints:
        snapshot = checkpoint.state.get(
            "procedure_runtime_state"
        )

        if snapshot is None:
            continue

        state = (
            ProcedureRuntimeState
            .model_validate(snapshot)
        )

        if (
            state.current_step == 1
            and state.retry_count == 1
            and state.step_status == StepStatus.WAITING_APPROVAL
            and state.workflow_status == WorkflowStatus.WAITING_HUMAN
            and state.approval_status == ApprovalStatus.PENDING
            and state.approval_id == second_approval_id
        ):
            matching_states.append(state)

    assert len(matching_states) >= 1

    fresh_state = matching_states[-1]

    assert fresh_state.operation_result is None
    assert fresh_state.verification_result is None
    assert fresh_state.approval_id == second_approval_id