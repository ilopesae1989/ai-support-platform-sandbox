from importlib import (
    import_module,
)

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

from tests.workflows.incident_resolution.test_procedure_transition_gate import (
    make_context,
    make_state,
)


class FakeWorkflowContext:
    """
    Contexto mínimo para probar únicamente
    el adapter WorkflowContext -> Transition Gate.

    No simula Foundry.
    No simula MCP.
    No contiene lógica de transición.
    """

    def __init__(
        self,
        state: ProcedureRuntimeState | None,
    ) -> None:
        self.states = {}
        self.outputs = []

        if state is not None:
            self.states[
                PROCEDURE_RUNTIME_STATE_KEY
            ] = state.model_dump(
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
        self.states[
            key
        ] = value

    async def yield_output(
        self,
        value,
    ):
        self.outputs.append(
            value
        )


def get_executor():
    module = import_module(
        "src.workflows."
        "incident_resolution."
        "executors."
        "procedure_transition"
    )

    return (
        module
        .ProcedureTransitionExecutor()
    )


def load_stored_state(
    ctx,
) -> ProcedureRuntimeState:
    return (
        ProcedureRuntimeState
        .model_validate(
            ctx.states[
                PROCEDURE_RUNTIME_STATE_KEY
            ]
        )
    )


@pytest.mark.asyncio
async def test_transition_executor_applies_and_persists_gate_result():
    state = make_state()

    state_before = (
        state.model_dump(
            mode="json"
        )
    )

    context = make_context(
        validation_status="satisfied",
        proposed_next_action="continue",
    )

    ctx = FakeWorkflowContext(
        state
    )

    await get_executor().handle(
        context,
        ctx,
    )

    #
    # El objeto original recibido al crear el
    # contexto no se modifica.
    #
    assert (
        state.model_dump(
            mode="json"
        )
        == state_before
    )

    stored = (
        load_stored_state(
            ctx
        )
    )

    assert (
        stored.step_status
        == StepStatus.SUCCEEDED
    )

    assert (
        stored.workflow_status
        == WorkflowStatus.RUNNING
    )

    assert (
        stored.verification_result
        is not None
    )

    #
    # El executor terminal de FASE 16
    # produce exactamente un snapshot.
    #
    assert len(
        ctx.outputs
    ) == 1

    output = ctx.outputs[0]

    assert isinstance(
        output,
        ProcedureRuntimeState,
    )

    assert (
        output.model_dump(
            mode="json"
        )
        ==
        stored.model_dump(
            mode="json"
        )
    )


@pytest.mark.asyncio
async def test_transition_executor_missing_runtime_fails_closed():
    ctx = FakeWorkflowContext(
        None
    )

    context = make_context()

    with pytest.raises(
        RuntimeError,
        match="ProcedureRuntimeState",
    ):
        await get_executor().handle(
            context,
            ctx,
        )

    assert ctx.outputs == []

    assert (
        PROCEDURE_RUNTIME_STATE_KEY
        not in ctx.states
    )


@pytest.mark.asyncio
async def test_transition_executor_gate_failure_does_not_persist_or_output():
    state = make_state()

    #
    # Estado autoritativo manipulado después
    # de la operación.
    #
    # El ProcedureValidationContext conserva
    # el paso original, por lo que el gate
    # debe detectar la sustitución.
    #
    state.step.description = (
        "Tampered authoritative description."
    )

    ctx = FakeWorkflowContext(
        state
    )

    snapshot_before = dict(
        ctx.states[
            PROCEDURE_RUNTIME_STATE_KEY
        ]
    )

    context = make_context()

    with pytest.raises(
        ValueError,
        match="ProcedureValidationStep",
    ):
        await get_executor().handle(
            context,
            ctx,
        )

    assert (
        ctx.states[
            PROCEDURE_RUNTIME_STATE_KEY
        ]
        == snapshot_before
    )

    assert ctx.outputs == []


@pytest.mark.asyncio
async def test_transition_executor_repeat_persists_fresh_operation_boundary():
    state = make_state()

    ctx = FakeWorkflowContext(
        state
    )

    context = make_context(
        validation_status="not_satisfied",
        proposed_next_action="repeat",
    )

    await get_executor().handle(
        context,
        ctx,
    )

    stored = (
        load_stored_state(
            ctx
        )
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

    #
    # REPEAT no conserva autorización
    # de la operación anterior.
    #
    assert stored.approval_id is None

    assert (
        stored.approval_status
        == ApprovalStatus.PENDING
    )

    assert stored.resolved_parameters == []

    assert stored.operation_result is None

    assert (
        stored.verification_result
        is None
    )

    assert len(
        ctx.outputs
    ) == 1
