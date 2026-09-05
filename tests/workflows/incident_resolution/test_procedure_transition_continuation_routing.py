import inspect

import pytest

from src.runtime.procedure.models import (
    ApprovalStatus,
    ProcedureRuntimeState,
    StepStatus,
    WorkflowStatus,
)

from src.runtime.procedure.workflow_state import (
    PROCEDURE_RUNTIME_STATE_KEY,
)

from src.workflows.incident_resolution.continuation_context import (
    PROCEDURE_CONTINUATION_CONTEXT_STATE_KEY,
    ProcedureContinuationContext,
)

from src.workflows.incident_resolution.models import (
    ProcedureExecutionInput,
)

from tests.workflows.incident_resolution.test_procedure_transition_gate import (
    make_context,
    make_state,
)


class FakeWorkflowContext:
    def __init__(
        self,
        state,
        continuation=None,
    ):
        self.states = {}
        self.outputs = []
        self.messages = []
        self.events = []

        if state is not None:
            self.states[
                PROCEDURE_RUNTIME_STATE_KEY
            ] = state.model_dump(
                mode="json"
            )

        if continuation is not None:
            self.states[
                PROCEDURE_CONTINUATION_CONTEXT_STATE_KEY
            ] = continuation.model_dump(
                mode="json"
            )

    def get_state(
        self,
        key,
        default=None,
    ):
        return self.states.get(
            key,
            default,
        )

    def set_state(
        self,
        key,
        value,
    ):
        self.states[key] = value

        self.events.append(
            (
                "set_state",
                key,
            )
        )

    async def send_message(
        self,
        message,
        target_id=None,
    ):
        stored = (
            ProcedureRuntimeState
            .model_validate(
                self.states[
                    PROCEDURE_RUNTIME_STATE_KEY
                ]
            )
        )

        assert (
            stored.workflow_status
            == WorkflowStatus.RUNNING
        )

        assert stored.step_status in {
            StepStatus.SUCCEEDED,
            StepStatus.PENDING,
        }

        self.messages.append(
            (
                message,
                target_id,
            )
        )

        self.events.append(
            (
                "send_message",
                target_id,
            )
        )

    async def yield_output(
        self,
        value,
    ):
        self.outputs.append(
            value
        )

        self.events.append(
            (
                "yield_output",
                None,
            )
        )


def make_continuation(
    *,
    procedure_found=True,
    procedure_match="exact",
    execution_eligible=True,
):
    return ProcedureContinuationContext(
        request_affected_resource="subscription",

        incident_description=(
            "Continuation routing test."
        ),

        procedure_found=procedure_found,
        procedure_match=procedure_match,
        execution_eligible=execution_eligible,

        operational_affected_resource=(
            "subscription"
        ),

        resource_type=None,
        service=None,
        environment=None,
        incident_origin="observed",

        subscription_id=(
            "557fdabc-f3b6-4c24-"
            "a9ae-e9e89b5ad172"
        ),

        resource_group=None,
        vm_name=None,
        tenant_id=None,
    )


def get_executor():
    from src.workflows.incident_resolution.executors.procedure_transition import (
        ProcedureTransitionExecutor,
    )

    return ProcedureTransitionExecutor()


def load_stored_state(
    ctx,
):
    return (
        ProcedureRuntimeState
        .model_validate(
            ctx.states[
                PROCEDURE_RUNTIME_STATE_KEY
            ]
        )
    )


def test_transition_executor_source_uses_explicit_outcome_and_continuation_builder():
    from src.workflows.incident_resolution.executors.procedure_transition import (
        ProcedureTransitionExecutor,
    )

    source = inspect.getsource(
        ProcedureTransitionExecutor.handle
    )

    assert (
        "apply_procedure_validation_transition_with_outcome"
        in source
    )

    assert (
        "load_procedure_continuation_context"
        in source
    )

    assert (
        "build_procedure_continuation_input"
        in source
    )

    assert (
        "ctx.send_message"
        in source
    )

    assert (
        'target_id="procedure_execution"'
        in source
    )

    assert (
        "apply_procedure_validation_transition("
        not in source
    )


@pytest.mark.asyncio
async def test_continue_persists_then_sends_exact_n_plus_one_without_terminal_output():
    state = make_state()

    ctx = FakeWorkflowContext(
        state,
        make_continuation(),
    )

    await get_executor().handle(
        make_context(
            validation_status="satisfied",
            proposed_next_action="continue",
        ),
        ctx,
    )

    stored = load_stored_state(
        ctx
    )

    assert stored.current_step == 1

    assert (
        stored.step_status
        == StepStatus.SUCCEEDED
    )

    assert (
        stored.workflow_status
        == WorkflowStatus.RUNNING
    )

    assert len(ctx.messages) == 1
    assert ctx.outputs == []

    message, target_id = (
        ctx.messages[0]
    )

    assert isinstance(
        message,
        ProcedureExecutionInput,
    )

    assert target_id == "procedure_execution"

    assert (
        message.request.requested_step
        == 2
    )

    assert (
        message.request.procedure_id
        == stored.procedure.id
    )

    assert (
        message.request.procedure_version
        == stored.procedure.version
    )

    assert (
        message.execution_identity.workflow_id
        == stored.workflow_id
    )

    assert (
        message.execution_identity.alert_id
        == stored.alert_id
    )

    assert (
        message.operational_context.alert_id
        == stored.alert_id
    )

    assert ctx.events[-2:] == [
        (
            "set_state",
            PROCEDURE_RUNTIME_STATE_KEY,
        ),
        (
            "send_message",
            "procedure_execution",
        ),
    ]


@pytest.mark.asyncio
async def test_continue_without_durable_continuation_context_fails_closed_after_persist_before_send():
    state = make_state()

    ctx = FakeWorkflowContext(
        state,
        continuation=None,
    )

    with pytest.raises(
        RuntimeError,
        match="ProcedureContinuationContext",
    ):
        await get_executor().handle(
            make_context(
                validation_status="satisfied",
                proposed_next_action="continue",
            ),
            ctx,
        )

    stored = load_stored_state(
        ctx
    )

    assert (
        stored.step_status
        == StepStatus.SUCCEEDED
    )

    assert (
        stored.workflow_status
        == WorkflowStatus.RUNNING
    )

    assert ctx.messages == []
    assert ctx.outputs == []


@pytest.mark.asyncio
async def test_continue_rejects_non_admitted_snapshot_without_send_or_output():
    state = make_state()

    ctx = FakeWorkflowContext(
        state,
        make_continuation(
            procedure_found=False,
        ),
    )

    with pytest.raises(
        ValueError,
        match="admission",
    ):
        await get_executor().handle(
            make_context(
                validation_status="satisfied",
                proposed_next_action="continue",
            ),
            ctx,
        )

    stored = load_stored_state(
        ctx
    )

    assert (
        stored.step_status
        == StepStatus.SUCCEEDED
    )

    assert (
        stored.workflow_status
        == WorkflowStatus.RUNNING
    )

    assert ctx.messages == []
    assert ctx.outputs == []


@pytest.mark.asyncio
async def test_resolved_is_terminal_and_does_not_require_continuation_context():
    state = make_state()

    state.total_steps = 1
    state.current_step = 1

    ctx = FakeWorkflowContext(
        state,
        continuation=None,
    )

    await get_executor().handle(
        make_context(
            validation_status="satisfied",
            proposed_next_action="continue",
        ),
        ctx,
    )

    stored = load_stored_state(
        ctx
    )

    assert (
        stored.workflow_status
        == WorkflowStatus.RESOLVED
    )

    assert ctx.messages == []

    assert len(ctx.outputs) == 1

    assert (
        ctx.outputs[0]
        .workflow_status
        == WorkflowStatus.RESOLVED
    )


@pytest.mark.asyncio
async def test_repeat_routes_same_step_with_continuation_context():
    state = make_state()

    ctx = FakeWorkflowContext(
        state,
        continuation=make_continuation(),
    )

    await get_executor().handle(
        make_context(
            validation_status="not_satisfied",
            proposed_next_action="repeat",
        ),
        ctx,
    )

    stored = load_stored_state(
        ctx
    )

    assert (
        stored.step_status
        == StepStatus.PENDING
    )

    assert (
        stored.workflow_status
        == WorkflowStatus.RUNNING
    )

    assert stored.retry_count == 1

    assert stored.approval_id is None

    assert (
        stored.approval_status
        == ApprovalStatus.PENDING
    )

    assert stored.resolved_parameters == []
    assert stored.operation_result is None
    assert stored.verification_result is None

    assert ctx.outputs == []

    assert len(ctx.messages) == 1

    message, target_id = (
        ctx.messages[0]
    )

    assert isinstance(
        message,
        ProcedureExecutionInput,
    )

    assert (
        target_id
        == "procedure_execution"
    )

    assert (
        message.request.requested_step
        == stored.current_step
    )


@pytest.mark.asyncio
async def test_repeat_fails_closed_without_continuation_context():
    state = make_state()

    ctx = FakeWorkflowContext(
        state,
        continuation=None,
    )

    with pytest.raises(
        RuntimeError,
        match="ContinuationContext",
    ):
        await get_executor().handle(
            make_context(
                validation_status="not_satisfied",
                proposed_next_action="repeat",
            ),
            ctx,
        )

    stored = load_stored_state(
        ctx
    )

    assert (
        stored.step_status
        == StepStatus.PENDING
    )

    assert (
        stored.workflow_status
        == WorkflowStatus.RUNNING
    )

    assert stored.retry_count == 1
    assert stored.approval_id is None
    assert stored.operation_result is None
    assert stored.verification_result is None

    assert ctx.messages == []
    assert ctx.outputs == []
