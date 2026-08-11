import pytest

from agent_framework import (
    InMemoryCheckpointStorage,
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


async def create_checkpoint_with_pending_hitl():
    """
    Ejecuta un workflow nuevo hasta HITL y devuelve
    el checkpoint que contiene exactamente esa
    solicitud pendiente.

    La selección se realiza por semántica:
    pending_request_info_events != vacío.

    No dependemos del índice del checkpoint ni
    de un iteration_count concreto.
    """

    storage = (
        InMemoryCheckpointStorage()
    )

    agents = (
        AzureWorkflowFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    request_ids = []

    async for event in workflow.run(
        create_alert(),
        stream=True,
        checkpoint_storage=storage,
    ):
        if (
            event.type
            == "request_info"
        ):
            request_ids.append(
                event.request_id
            )

    assert request_ids
    assert len(request_ids) == 1

    original_request_id = (
        request_ids[0]
    )

    #
    # Antes de aprobación no existe ninguna
    # operación.
    #
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

    checkpoints = (
        await storage.list_checkpoints(
            workflow_name=workflow.name
        )
    )

    assert checkpoints

    hitl_checkpoints = [
        checkpoint
        for checkpoint in checkpoints
        if (
            checkpoint
            .pending_request_info_events
        )
    ]

    #
    # El probe de 1.13.0 ha demostrado que existe
    # un único checkpoint correspondiente al HITL
    # pendiente de este ciclo.
    #
    assert len(
        hitl_checkpoints
    ) == 1

    checkpoint = (
        hitl_checkpoints[0]
    )

    assert (
        original_request_id
        in checkpoint
        .pending_request_info_events
    )

    #
    # El runtime autoritativo del procedimiento
    # debe formar parte del checkpoint.
    #
    assert (
        "procedure_runtime_state"
        in checkpoint.state
    )

    return (
        storage,
        checkpoint,
        original_request_id,
    )


@pytest.mark.asyncio
async def test_restore_hitl_checkpoint_reemits_same_request_without_reexecution():
    """
    FASE 16.11.3

    Restaurar un checkpoint con HITL pendiente:

    - reemite exactamente la misma request;
    - conserva exactamente el request_id;
    - no reejecuta ningún agente cognitivo;
    - no ejecuta Azure;
    - no produce resultado operacional.

    Se utiliza deliberadamente un nuevo objeto
    Workflow para representar restart/recovery.
    """

    (
        storage,
        checkpoint,
        original_request_id,
    ) = (
        await create_checkpoint_with_pending_hitl()
    )

    #
    # Simulamos restart:
    # nuevos agents + nuevo Workflow.
    #
    resumed_agents = (
        AzureWorkflowFakeFoundryAgents()
    )

    resumed_workflow = (
        build_incident_resolution_workflow(
            agents=resumed_agents,
        )
    )

    resumed_request_ids = []
    outputs = []

    async for event in resumed_workflow.run(
        checkpoint_id=(
            checkpoint.checkpoint_id
        ),
        checkpoint_storage=storage,
        stream=True,
    ):
        if (
            event.type
            == "request_info"
        ):
            resumed_request_ids.append(
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
    # Una restauración no reconstruye el camino
    # cognitivo ya consumido.
    #
    assert (
        resumed_agents.calls
        == []
    )

    #
    # No existe operación ni output por el mero
    # hecho de restaurar.
    #
    assert (
        "azure_operations"
        not in resumed_agents.calls
    )

    assert outputs == []

    #
    # El HITL pendiente se reemite exactamente
    # una vez y conserva su identidad.
    #
    assert resumed_request_ids == [
        original_request_id,
    ]

    assert (
        original_request_id
        in checkpoint
        .pending_request_info_events
    )
