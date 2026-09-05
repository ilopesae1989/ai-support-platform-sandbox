import pytest

from agent_framework import (
    Executor,
    WorkflowBuilder,
    WorkflowContext,
    handler,
)

from src.runtime.procedure.models import (
    ProcedureRuntimeState,
)

from src.runtime.procedure.workflow_state import (
    store_procedure_runtime_state,
)

from src.workflows.incident_resolution.checkpoint_storage import (
    build_incident_checkpoint_storage,
    incident_checkpoint_allowed_types,
)

from src.workflows.incident_resolution.executors.azure_vm_post_operation_observation import (
    AzureVmPostOperationObservationExecutor,
)

from src.workflows.incident_resolution.executors.procedure_transition import (
    ProcedureTransitionExecutor,
)

from src.workflows.incident_resolution.procedure_validation_models import (
    ProcedureValidationContext,
)

from src.workflows.incident_resolution.wait_recheck import (
    WaitRecheckRequest,
)

from tests.workflows.incident_resolution.test_procedure_wait_recheck_contract import (
    _context,
    _state,
)


WAIT_REQUEST_TYPE = (
    "src.workflows.incident_resolution."
    "wait_recheck:WaitRecheckRequest"
)

WAIT_SIGNAL_TYPE = (
    "src.workflows.incident_resolution."
    "wait_recheck:WaitRecheckSignal"
)


class WaitCheckpointSeedExecutor(
    Executor
):
    def __init__(
        self,
    ) -> None:
        super().__init__(
            id="wait_checkpoint_seed"
        )

    @handler
    async def handle(
        self,
        message: str,
        ctx: WorkflowContext[
            ProcedureValidationContext,
            ProcedureRuntimeState,
        ],
    ) -> None:
        if message != "start":
            raise RuntimeError(
                "Unexpected checkpoint test input."
            )

        state = _state()

        store_procedure_runtime_state(
            ctx,
            state,
        )

        await ctx.send_message(
            _context()
        )


def _build_wait_checkpoint_workflow():
    seed = (
        WaitCheckpointSeedExecutor()
    )

    transition = (
        ProcedureTransitionExecutor()
    )

    observation = (
        AzureVmPostOperationObservationExecutor(
            reader=None
        )
    )

    return (
        WorkflowBuilder(
            start_executor=seed,
            name="wait-recheck-checkpoint-contract",
        )
        .add_edge(
            seed,
            transition,
        )
        .add_edge(
            transition,
            observation,
        )
        .build()
    )


def test_wait_recheck_checkpoint_types_are_explicitly_allowlisted():
    allowed = (
        incident_checkpoint_allowed_types()
    )

    assert (
        WAIT_REQUEST_TYPE
        in allowed
    )

    assert (
        WAIT_SIGNAL_TYPE
        in allowed
    )


@pytest.mark.asyncio
async def test_pending_wait_recheck_request_survives_checkpoint_restart(
    tmp_path,
):
    storage = (
        build_incident_checkpoint_storage(
            tmp_path
            / "checkpoints"
        )
    )

    workflow_a = (
        _build_wait_checkpoint_workflow()
    )

    original_requests = []

    async for event in workflow_a.run(
        "start",
        stream=True,
        checkpoint_storage=storage,
    ):
        if event.type == "request_info":
            original_requests.append(
                event
            )

    assert len(
        original_requests
    ) == 1

    original_event = (
        original_requests[0]
    )

    assert isinstance(
        original_event.data,
        WaitRecheckRequest,
    )

    assert (
        original_event.request_id
        == original_event.data.recheck_id
    )

    checkpoints = (
        await storage.list_checkpoints(
            workflow_name=workflow_a.name
        )
    )

    pending = [
        checkpoint
        for checkpoint
        in checkpoints
        if (
            original_event.request_id
            in checkpoint
            .pending_request_info_events
        )
    ]

    assert len(
        pending
    ) == 1

    pending_checkpoint = (
        pending[0]
    )

    workflow_b = (
        _build_wait_checkpoint_workflow()
    )

    restored_requests = []

    async for event in workflow_b.run(
        checkpoint_id=(
            pending_checkpoint
            .checkpoint_id
        ),
        stream=True,
        checkpoint_storage=storage,
    ):
        if event.type == "request_info":
            restored_requests.append(
                event
            )

    assert len(
        restored_requests
    ) == 1

    restored_event = (
        restored_requests[0]
    )

    assert (
        restored_event.request_id
        == original_event.request_id
    )

    assert isinstance(
        restored_event.data,
        WaitRecheckRequest,
    )

    assert (
        restored_event.data
        == original_event.data
    )

    assert (
        restored_event.data.recheck_id
        == original_event.data.recheck_id
    )

    assert (
        restored_event.data.operation_id
        == original_event.data.operation_id
    )

    assert (
        restored_event.data.workflow_id
        == original_event.data.workflow_id
    )

    assert (
        restored_event.data.current_step
        == original_event.data.current_step
    )

    assert (
        restored_event.data.recheck_count
        == 1
    )