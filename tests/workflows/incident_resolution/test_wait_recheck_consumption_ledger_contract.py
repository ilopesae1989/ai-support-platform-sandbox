import importlib

import pytest

from agent_framework import (
    Executor,
    InMemoryCheckpointStorage,
    WorkflowBuilder,
    WorkflowContext,
    handler,
)

from src.runtime.procedure.models import (
    ProcedureRuntimeState,
)

from src.runtime.procedure.workflow_state import (
    PROCEDURE_RUNTIME_STATE_KEY,
    store_procedure_runtime_state,
)

from src.workflows.incident_resolution.executors.procedure_transition import (
    ProcedureTransitionExecutor,
)

from src.workflows.incident_resolution.procedure_transition_gate import (
    apply_procedure_validation_transition_with_outcome,
)

from src.workflows.incident_resolution.procedure_validation_models import (
    ProcedureValidationContext,
    ProcedureValidationRequest,
)

from src.workflows.incident_resolution.wait_recheck import (
    WaitRecheckSignal,
    build_wait_recheck_request,
)

from tests.workflows.incident_resolution.test_procedure_wait_recheck_contract import (
    _context,
    _state,
)


LEDGER_MODULE = (
    "src.workflows.incident_resolution."
    "wait_recheck_consumption_ledger"
)


def _load_ledger_module():
    return importlib.import_module(
        LEDGER_MODULE
    )


def test_wait_recheck_consumption_authority_is_separate_contract():
    module = _load_ledger_module()

    assert hasattr(
        module,
        "WaitRecheckConsumptionLedger",
    )

    assert hasattr(
        module,
        "WaitRecheckAlreadyConsumedError",
    )

    assert hasattr(
        module,
        "InMemoryWaitRecheckConsumptionLedger",
    )

    assert hasattr(
        module,
        "SqliteWaitRecheckConsumptionLedger",
    )

    source = (
        importlib
        .import_module(
            LEDGER_MODULE
        )
        .__dict__
    )

    names = set(
        source
    )

    assert (
        "OperationDispatchLedger"
        not in names
    )

    assert (
        "IncidentContinuationStore"
        not in names
    )

    assert (
        "PendingApprovalStore"
        not in names
    )


def test_in_memory_wait_recheck_claim_is_monotonic():
    module = _load_ledger_module()

    ledger = (
        module
        .InMemoryWaitRecheckConsumptionLedger()
    )

    error_type = (
        module
        .WaitRecheckAlreadyConsumedError
    )

    recheck_id = (
        "rchk-monotonic-001"
    )

    assert (
        ledger.contains(
            recheck_id
        )
        is False
    )

    ledger.claim(
        recheck_id
    )

    assert (
        ledger.contains(
            recheck_id
        )
        is True
    )

    assert ledger.count() == 1

    with pytest.raises(
        error_type
    ):
        ledger.claim(
            recheck_id
        )

    assert ledger.count() == 1


def test_sqlite_wait_recheck_claim_survives_new_instance(
    tmp_path,
):
    module = _load_ledger_module()

    ledger_type = (
        module
        .SqliteWaitRecheckConsumptionLedger
    )

    error_type = (
        module
        .WaitRecheckAlreadyConsumedError
    )

    path = (
        tmp_path
        / "wait-recheck-ledger.db"
    )

    recheck_id = (
        "rchk-sqlite-001"
    )

    ledger_a = ledger_type(
        path
    )

    ledger_a.claim(
        recheck_id
    )

    assert (
        ledger_a.contains(
            recheck_id
        )
        is True
    )

    ledger_b = ledger_type(
        path
    )

    assert (
        ledger_b.contains(
            recheck_id
        )
        is True
    )

    with pytest.raises(
        error_type
    ):
        ledger_b.claim(
            recheck_id
        )


class RejectingLedger:
    def __init__(
        self,
        *,
        error_type,
    ):
        self.error_type = error_type
        self.claimed = []

    def claim(
        self,
        recheck_id,
    ):
        self.claimed.append(
            recheck_id
        )

        raise self.error_type(
            "recheck already consumed"
        )

    def contains(
        self,
        recheck_id,
    ):
        return True


class ResponseContext:
    def __init__(
        self,
        state,
    ):
        self.state = {
            PROCEDURE_RUNTIME_STATE_KEY:
                state.model_dump(
                    mode="json"
                )
        }

        self.messages = []

    def get_state(
        self,
        key,
        default=None,
    ):
        return self.state.get(
            key,
            default,
        )

    def set_state(
        self,
        key,
        value,
    ):
        self.state[key] = value

    async def send_message(
        self,
        value,
        target_id=None,
    ):
        self.messages.append(
            (
                value,
                target_id,
            )
        )


def _wait_state_and_request():
    outcome = (
        apply_procedure_validation_transition_with_outcome(
            state=_state(),
            context=_context(),
        )
    )

    state = outcome.state

    request = (
        build_wait_recheck_request(
            state
        )
    )

    return (
        state,
        request,
    )


@pytest.mark.asyncio
async def test_transition_claims_recheck_before_mutating_runtime_or_routing():
    module = _load_ledger_module()

    error_type = (
        module
        .WaitRecheckAlreadyConsumedError
    )

    (
        state,
        request,
    ) = _wait_state_and_request()

    signal = WaitRecheckSignal(
        recheck_id=(
            request.recheck_id
        )
    )

    ledger = RejectingLedger(
        error_type=error_type
    )

    executor = (
        ProcedureTransitionExecutor(
            wait_recheck_consumption_ledger=(
                ledger
            )
        )
    )

    ctx = ResponseContext(
        state
    )

    snapshot_before = dict(
        ctx.state
    )

    with pytest.raises(
        error_type
    ):
        await executor.handle_wait_recheck_response(
            request,
            signal,
            ctx,
        )

    assert ledger.claimed == [
        request.recheck_id
    ]

    assert ctx.state == snapshot_before
    assert ctx.messages == []


class WaitSeedExecutor(
    Executor
):
    def __init__(
        self,
    ) -> None:
        super().__init__(
            id="wait_ledger_seed"
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
                "Unexpected test input."
            )

        store_procedure_runtime_state(
            ctx,
            _state(),
        )

        await ctx.send_message(
            _context()
        )


class ObservationCaptureExecutor(
    Executor
):
    def __init__(
        self,
    ) -> None:
        super().__init__(
            id=(
                "azure_vm_post_operation_observation"
            )
        )

        self.messages = []

    @handler
    async def handle(
        self,
        message: ProcedureValidationRequest,
        ctx: WorkflowContext[
            ProcedureValidationRequest
        ],
    ) -> None:
        self.messages.append(
            message
        )


def _build_replay_workflow(
    ledger,
):
    seed = WaitSeedExecutor()

    transition = (
        ProcedureTransitionExecutor(
            wait_recheck_consumption_ledger=(
                ledger
            )
        )
    )

    capture = (
        ObservationCaptureExecutor()
    )

    workflow = (
        WorkflowBuilder(
            start_executor=seed,
            max_iterations=100,
            name=(
                "wait-recheck-ledger-replay"
            ),
        )
        .add_edge(
            seed,
            transition,
        )
        .add_edge(
            transition,
            capture,
        )
        .build()
    )

    return (
        workflow,
        capture,
    )


@pytest.mark.asyncio
async def test_shared_monotonic_ledger_blocks_historical_pending_checkpoint_replay():
    module = _load_ledger_module()

    ledger = (
        module
        .InMemoryWaitRecheckConsumptionLedger()
    )

    error_type = (
        module
        .WaitRecheckAlreadyConsumedError
    )

    storage = (
        InMemoryCheckpointStorage()
    )

    (
        workflow_a,
        _,
    ) = _build_replay_workflow(
        ledger
    )

    requests = []

    async for event in workflow_a.run(
        "start",
        stream=True,
        checkpoint_storage=storage,
    ):
        if event.type == "request_info":
            requests.append(
                event
            )

    assert len(requests) == 1

    request_event = requests[0]

    request_id = (
        request_event.request_id
    )

    request = (
        request_event.data
    )

    signal = WaitRecheckSignal(
        recheck_id=(
            request.recheck_id
        )
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
            request_id
            in checkpoint
            .pending_request_info_events
        )
    ]

    assert len(pending) == 1

    pending_checkpoint = (
        pending[0]
    )

    (
        workflow_b,
        capture_b,
    ) = _build_replay_workflow(
        ledger
    )

    async for _ in workflow_b.run(
        checkpoint_id=(
            pending_checkpoint
            .checkpoint_id
        ),
        responses={
            request_id:
                signal
        },
        stream=True,
        checkpoint_storage=storage,
    ):
        pass

    assert len(
        capture_b.messages
    ) == 1

    assert (
        ledger.contains(
            request.recheck_id
        )
        is True
    )

    assert ledger.count() == 1

    (
        workflow_c,
        capture_c,
    ) = _build_replay_workflow(
        ledger
    )

    with pytest.raises(
        error_type
    ):
        async for _ in workflow_c.run(
            checkpoint_id=(
                pending_checkpoint
                .checkpoint_id
            ),
            responses={
                request_id:
                    signal
            },
            stream=True,
            checkpoint_storage=storage,
        ):
            pass

    assert capture_c.messages == []

    assert ledger.count() == 1