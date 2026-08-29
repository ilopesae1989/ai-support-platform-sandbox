from __future__ import annotations

import pytest

from src.workflows.incident_resolution.checkpoint_storage import (
    build_incident_checkpoint_storage,
)

from src.workflows.incident_resolution.operation_dispatch_ledger import (
    OperationAlreadyDispatchedError,
    SqliteOperationDispatchLedger,
)

from src.workflows.incident_resolution.workflow import (
    build_incident_resolution_workflow,
)

from tests.workflows.incident_resolution.test_checkpoint_operation_resume import (
    checkpoint_emitted_by,
)

from tests.workflows.incident_resolution.test_incident_workflow import (
    create_alert,
)

from tests.workflows.incident_resolution.test_incident_workflow_azure_operations import (
    AzureWorkflowFakeFoundryAgents,
)


async def run_fresh_until_hitl(
    *,
    checkpoint_path,
    ledger_path,
):
    storage = (
        build_incident_checkpoint_storage(
            checkpoint_path
        )
    )

    ledger = (
        SqliteOperationDispatchLedger(
            ledger_path
        )
    )

    agents = (
        AzureWorkflowFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
            operation_dispatch_ledger=(
                ledger
            ),
        )
    )

    requests = []
    outputs = []

    async for event in workflow.run(
        create_alert(),
        checkpoint_storage=storage,
        stream=True,
    ):
        if event.type == "request_info":
            requests.append(
                event
            )

        elif event.type == "output":
            outputs.append(
                event.data
            )

    assert outputs == []

    assert len(
        requests
    ) == 1

    request = (
        requests[0]
    )

    checkpoints = (
        await storage.list_checkpoints(
            workflow_name=(
                workflow.name
            )
        )
    )

    hitl_matches = [
        checkpoint
        for checkpoint in checkpoints
        if (
            request.request_id
            in (
                checkpoint
                .pending_request_info_events
            )
        )
    ]

    assert len(
        hitl_matches
    ) == 1

    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
    ]

    assert (
        "azure_operations"
        not in agents.calls
    )

    return (
        request,
        hitl_matches[0],
    )


async def restore_pending_hitl_after_restart(
    *,
    checkpoint_path,
    ledger_path,
    hitl_checkpoint,
    request_id,
):
    #
    # NUEVA instancia de ambos backends.
    #
    storage = (
        build_incident_checkpoint_storage(
            checkpoint_path
        )
    )

    ledger = (
        SqliteOperationDispatchLedger(
            ledger_path
        )
    )

    agents = (
        AzureWorkflowFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
            operation_dispatch_ledger=(
                ledger
            ),
        )
    )

    requests = []
    outputs = []

    async for event in workflow.run(
        checkpoint_id=(
            hitl_checkpoint
            .checkpoint_id
        ),
        checkpoint_storage=storage,
        stream=True,
    ):
        if event.type == "request_info":
            requests.append(
                event
            )

        elif event.type == "output":
            outputs.append(
                event.data
            )

    assert outputs == []

    assert len(
        requests
    ) == 1

    assert (
        requests[0].request_id
        == request_id
    )

    assert agents.calls == []

    return (
        storage,
        workflow,
        agents,
    )


async def approve_after_restart(
    *,
    storage,
    workflow,
    agents,
    request_id,
):
    outputs = []
    unexpected_requests = []

    async for event in workflow.run(
        responses={
            request_id:
                True,
        },
        checkpoint_storage=storage,
        stream=True,
    ):
        if event.type == "output":
            outputs.append(
                event.data
            )

        elif event.type == "request_info":
            unexpected_requests.append(
                event
            )

    assert unexpected_requests == []

    assert len(
        outputs
    ) == 1

    assert agents.calls == [
        "azure_operations",
        "procedure_validation",
    ]

    assert (
        agents.calls.count(
            "azure_operations"
        )
        == 1
    )

    checkpoints = (
        await storage.list_checkpoints(
            workflow_name=(
                workflow.name
            )
        )
    )

    assert checkpoints

    return checkpoints


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "historical_executor_id",
    [
        "azure_pre_call_security",
        "operation_start",
    ],
)
async def test_sqlite_dispatch_blocks_historical_replay_after_real_restart(
    tmp_path,
    historical_executor_id,
):
    checkpoint_path = (
        tmp_path
        / "incident-checkpoints"
    )

    ledger_path = (
        tmp_path
        / "operation-dispatch.db"
    )

    #
    # ==================================================
    # PROCESO A
    # fresh execution hasta HITL.
    # ==================================================
    #
    (
        request_event,
        hitl_checkpoint,
    ) = await run_fresh_until_hitl(
        checkpoint_path=(
            checkpoint_path
        ),
        ledger_path=(
            ledger_path
        ),
    )

    #
    # ==================================================
    # PROCESO B
    # nuevas instancias de storage + ledger + workflow.
    # ==================================================
    #
    (
        storage_b,
        workflow_b,
        agents_b,
    ) = await (
        restore_pending_hitl_after_restart(
            checkpoint_path=(
                checkpoint_path
            ),
            ledger_path=(
                ledger_path
            ),
            hitl_checkpoint=(
                hitl_checkpoint
            ),
            request_id=(
                request_event.request_id
            ),
        )
    )

    checkpoints = await approve_after_restart(
        storage=storage_b,
        workflow=workflow_b,
        agents=agents_b,
        request_id=(
            request_event.request_id
        ),
    )

    #
    # La operación YA ha sido reclamada de forma
    # durable en SQLite y Azure fake se alcanzó
    # exactamente una vez.
    #
    assert (
        agents_b.calls.count(
            "azure_operations"
        )
        == 1
    )

    historical_checkpoint = (
        checkpoint_emitted_by(
            checkpoints,
            historical_executor_id,
        )
    )

    assert (
        historical_checkpoint
        is not None
    )

    #
    # ==================================================
    # PROCESO C / ATAQUE
    #
    # Otra instancia nueva de TODO:
    #
    # - storage;
    # - ledger;
    # - workflow;
    # - agents.
    #
    # La única memoria común son los ficheros
    # durables.
    # ==================================================
    #
    storage_c = (
        build_incident_checkpoint_storage(
            checkpoint_path
        )
    )

    ledger_c = (
        SqliteOperationDispatchLedger(
            ledger_path
        )
    )

    agents_c = (
        AzureWorkflowFakeFoundryAgents()
    )

    workflow_c = (
        build_incident_resolution_workflow(
            agents=agents_c,
            operation_dispatch_ledger=(
                ledger_c
            ),
        )
    )

    replay_outputs = []
    replay_requests = []

    with pytest.raises(
        OperationAlreadyDispatchedError
    ):
        async for event in workflow_c.run(
            checkpoint_id=(
                historical_checkpoint
                .checkpoint_id
            ),
            checkpoint_storage=(
                storage_c
            ),
            stream=True,
        ):
            if event.type == "output":
                replay_outputs.append(
                    event.data
                )

            elif event.type == "request_info":
                replay_requests.append(
                    event
                )

    #
    # CRÍTICO:
    #
    # El claim SQLite debe bloquear antes de
    # que el fake de Azure Operations sea llamado.
    #
    assert (
        "azure_operations"
        not in agents_c.calls
    )

    assert (
        "procedure_validation"
        not in agents_c.calls
    )

    assert replay_outputs == []

    assert replay_requests == []

    #
    # CUARTO proceso:
    # demostrar que el consumo continúa durable
    # incluso después del ataque anterior.
    #
    ledger_d = (
        SqliteOperationDispatchLedger(
            ledger_path
        )
    )

    #
    # No conocemos ni inventamos operation_id aquí.
    # La prueba autoritativa de persistencia es que
    # el mismo checkpoint histórico vuelve a quedar
    # bloqueado al atravesar el executor real.
    #
    agents_d = (
        AzureWorkflowFakeFoundryAgents()
    )

    workflow_d = (
        build_incident_resolution_workflow(
            agents=agents_d,
            operation_dispatch_ledger=(
                ledger_d
            ),
        )
    )

    storage_d = (
        build_incident_checkpoint_storage(
            checkpoint_path
        )
    )

    with pytest.raises(
        OperationAlreadyDispatchedError
    ):
        async for _ in workflow_d.run(
            checkpoint_id=(
                historical_checkpoint
                .checkpoint_id
            ),
            checkpoint_storage=(
                storage_d
            ),
            stream=True,
        ):
            pass

    assert (
        "azure_operations"
        not in agents_d.calls
    )
