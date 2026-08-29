from __future__ import annotations

import pytest

from src.runtime.procedure.workflow import (
    ApprovalOutcome,
)

from src.workflows.incident_resolution.checkpoint_storage import (
    build_incident_checkpoint_storage,
)

from src.workflows.incident_resolution.workflow import (
    build_incident_resolution_workflow,
)

from tests.workflows.incident_resolution.test_incident_workflow import (
    create_alert,
)

from tests.workflows.incident_resolution.test_incident_workflow_azure_operations import (
    AzureWorkflowFakeFoundryAgents,
)


async def run_until_hitl(
    *,
    storage,
):
    agents = (
        AzureWorkflowFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    request_events = []

    async for event in workflow.run(
        create_alert(),
        stream=True,
        checkpoint_storage=storage,
    ):
        if (
            event.type
            == "request_info"
        ):
            request_events.append(
                event
            )

    assert len(
        request_events
    ) == 1

    request_event = (
        request_events[0]
    )

    #
    # list_checkpoints() fuerza lectura real
    # desde FileCheckpointStorage.
    #
    checkpoints = (
        await storage.list_checkpoints(
            workflow_name=(
                workflow.name
            )
        )
    )

    assert checkpoints

    hitl_matches = [
        checkpoint
        for checkpoint in checkpoints
        if (
            request_event.request_id
            in (
                checkpoint
                .pending_request_info_events
            )
        )
    ]

    assert len(
        hitl_matches
    ) == 1

    return (
        agents,
        workflow,
        request_event,
        hitl_matches[0],
    )


async def restore_hitl(
    *,
    checkpoint_path,
    checkpoint_id,
    request_id,
):
    #
    # Nueva instancia de storage:
    # simula restart / otro worker.
    #
    storage = (
        build_incident_checkpoint_storage(
            checkpoint_path
        )
    )

    agents = (
        AzureWorkflowFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    request_events = []
    outputs = []

    async for event in workflow.run(
        checkpoint_id=checkpoint_id,
        checkpoint_storage=storage,
        stream=True,
    ):
        if (
            event.type
            == "request_info"
        ):
            request_events.append(
                event
            )

        elif (
            event.type
            == "output"
        ):
            outputs.append(
                event.data
            )

    assert outputs == []

    assert len(
        request_events
    ) == 1

    assert (
        request_events[0].request_id
        == request_id
    )

    return (
        storage,
        agents,
        workflow,
    )


@pytest.mark.asyncio
async def test_file_storage_roundtrip_approved_incident(
    tmp_path,
):
    checkpoint_path = (
        tmp_path
        / "approved-incident"
    )

    storage_a = (
        build_incident_checkpoint_storage(
            checkpoint_path
        )
    )

    (
        initial_agents,
        _,
        request_event,
        hitl_checkpoint,
    ) = await run_until_hitl(
        storage=storage_a
    )

    assert initial_agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
    ]

    (
        storage_b,
        resumed_agents,
        resumed_workflow,
    ) = await restore_hitl(
        checkpoint_path=checkpoint_path,
        checkpoint_id=(
            hitl_checkpoint
            .checkpoint_id
        ),
        request_id=(
            request_event
            .request_id
        ),
    )

    outputs = []
    unexpected_requests = []

    async for event in resumed_workflow.run(
        responses={
            request_event.request_id:
                True,
        },
        checkpoint_storage=(
            storage_b
        ),
        stream=True,
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
            unexpected_requests.append(
                event
            )

    assert unexpected_requests == []

    assert len(outputs) == 1

    assert resumed_agents.calls == [
        "azure_operations",
        "procedure_validation",
    ]

    #
    # TERCERA instancia de storage.
    #
    # Aquí obligamos a deserializar también
    # los checkpoints post-HITL/post-operación.
    #
    storage_c = (
        build_incident_checkpoint_storage(
            checkpoint_path
        )
    )

    reloaded = (
        await storage_c.list_checkpoints(
            workflow_name=(
                resumed_workflow.name
            )
        )
    )

    assert reloaded

    assert any(
        (
            "procedure_runtime_state"
            in checkpoint.state
        )
        for checkpoint in reloaded
    )


@pytest.mark.asyncio
async def test_file_storage_roundtrip_rejected_incident(
    tmp_path,
):
    checkpoint_path = (
        tmp_path
        / "rejected-incident"
    )

    storage_a = (
        build_incident_checkpoint_storage(
            checkpoint_path
        )
    )

    (
        initial_agents,
        _,
        request_event,
        hitl_checkpoint,
    ) = await run_until_hitl(
        storage=storage_a
    )

    assert initial_agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
    ]

    (
        storage_b,
        resumed_agents,
        resumed_workflow,
    ) = await restore_hitl(
        checkpoint_path=checkpoint_path,
        checkpoint_id=(
            hitl_checkpoint
            .checkpoint_id
        ),
        request_id=(
            request_event
            .request_id
        ),
    )

    outputs = []
    unexpected_requests = []

    async for event in resumed_workflow.run(
        responses={
            request_event.request_id:
                False,
        },
        checkpoint_storage=(
            storage_b
        ),
        stream=True,
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
            unexpected_requests.append(
                event
            )

    assert unexpected_requests == []

    assert len(outputs) == 1

    assert isinstance(
        outputs[0],
        ApprovalOutcome,
    )

    assert (
        outputs[0].approved
        is False
    )

    assert (
        "azure_operations"
        not in resumed_agents.calls
    )

    #
    # Reabrir de nuevo desde disco y
    # deserializar todos los checkpoints.
    #
    storage_c = (
        build_incident_checkpoint_storage(
            checkpoint_path
        )
    )

    reloaded = (
        await storage_c.list_checkpoints(
            workflow_name=(
                resumed_workflow.name
            )
        )
    )

    assert reloaded
