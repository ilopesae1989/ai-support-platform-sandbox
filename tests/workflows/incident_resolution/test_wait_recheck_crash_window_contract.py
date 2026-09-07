import pytest

import src.workflows.incident_resolution.executors.procedure_transition as transition_module

from src.workflows.incident_resolution.executors.procedure_transition import (
    ProcedureTransitionExecutor,
)

from src.workflows.incident_resolution.wait_recheck import (
    WaitRecheckSignal,
)

from src.workflows.incident_resolution.wait_recheck_consumption_ledger import (
    SqliteWaitRecheckConsumptionLedger,
)

from tests.workflows.incident_resolution.test_wait_recheck_consumption_ledger_contract import (
    ResponseContext,
    _wait_state_and_request,
)


class SimulatedCrash(
    RuntimeError
):
    pass


class CrashBeforeSuperstepCheckpointContext(
    ResponseContext
):
    async def send_message(
        self,
        value,
        target_id=None,
    ):
        raise SimulatedCrash(
            "simulated crash after runtime "
            "state mutation and before "
            "response superstep checkpoint"
        )


def _signal(
    request,
):
    return WaitRecheckSignal(
        recheck_id=(
            request.recheck_id
        )
    )


def _executor(
    database_path,
):
    return ProcedureTransitionExecutor(
        wait_recheck_consumption_ledger=(
            SqliteWaitRecheckConsumptionLedger(
                database_path
            )
        )
    )


@pytest.mark.asyncio
async def test_same_wait_response_recovers_after_crash_between_durable_claim_and_runtime_state_persistence(
    monkeypatch,
    tmp_path,
):
    (
        waiting_state,
        request,
    ) = _wait_state_and_request()

    signal = _signal(
        request
    )

    database_path = (
        tmp_path
        / "crash-before-state.db"
    )

    first_executor = _executor(
        database_path
    )

    first_context = ResponseContext(
        waiting_state
    )

    original_store = (
        transition_module
        .store_procedure_runtime_state
    )

    def crash_before_state_persistence(
        ctx,
        candidate_state,
    ):
        raise SimulatedCrash(
            "simulated crash after durable "
            "claim and before runtime state "
            "persistence"
        )

    monkeypatch.setattr(
        transition_module,
        "store_procedure_runtime_state",
        crash_before_state_persistence,
    )

    with pytest.raises(
        SimulatedCrash
    ):
        await (
            first_executor
            .handle_wait_recheck_response(
                request,
                signal,
                first_context,
            )
        )

    assert first_context.messages == []

    monkeypatch.setattr(
        transition_module,
        "store_procedure_runtime_state",
        original_store,
    )

    restarted_executor = _executor(
        database_path
    )

    restored_response_entry_context = (
        ResponseContext(
            waiting_state
        )
    )

    await (
        restarted_executor
        .handle_wait_recheck_response(
            request,
            signal,
            restored_response_entry_context,
        )
    )

    assert len(
        restored_response_entry_context.messages
    ) == 1

    (
        _,
        target_id,
    ) = (
        restored_response_entry_context
        .messages[0]
    )

    assert (
        target_id
        == "azure_vm_post_operation_observation"
    )


@pytest.mark.asyncio
async def test_same_wait_response_recovers_after_crash_between_runtime_mutation_and_superstep_checkpoint(
    tmp_path,
):
    (
        waiting_state,
        request,
    ) = _wait_state_and_request()

    signal = _signal(
        request
    )

    database_path = (
        tmp_path
        / "crash-before-checkpoint.db"
    )

    first_executor = _executor(
        database_path
    )

    first_context = (
        CrashBeforeSuperstepCheckpointContext(
            waiting_state
        )
    )

    snapshot_before = dict(
        first_context.state
    )

    with pytest.raises(
        SimulatedCrash
    ):
        await (
            first_executor
            .handle_wait_recheck_response(
                request,
                signal,
                first_context,
            )
        )

    assert (
        first_context.state
        != snapshot_before
    )

    restored_response_entry_context = (
        ResponseContext(
            waiting_state
        )
    )

    restarted_executor = _executor(
        database_path
    )

    await (
        restarted_executor
        .handle_wait_recheck_response(
            request,
            signal,
            restored_response_entry_context,
        )
    )

    assert len(
        restored_response_entry_context.messages
    ) == 1

    (
        _,
        target_id,
    ) = (
        restored_response_entry_context
        .messages[0]
    )

    assert (
        target_id
        == "azure_vm_post_operation_observation"
    )