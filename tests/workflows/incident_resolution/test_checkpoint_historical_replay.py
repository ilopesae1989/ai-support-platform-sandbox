import pytest

from src.workflows.incident_resolution.operation_dispatch_ledger import (
    InMemoryOperationDispatchLedger,
    OperationAlreadyDispatchedError,
)

from src.workflows.incident_resolution.workflow import (
    build_incident_resolution_workflow,
)

from tests.workflows.incident_resolution.test_checkpoint_operation_resume import (
    checkpoint_emitted_by,
    create_completed_resumed_cycle,
)

from tests.workflows.incident_resolution.test_incident_workflow_azure_operations import (
    AzureWorkflowFakeFoundryAgents,
)


async def restore_historical_checkpoint(
    *,
    storage,
    checkpoint,
    operation_dispatch_ledger,
):
    """
    Restaura deliberadamente un checkpoint histórico
    perteneciente a una operación que YA terminó.

    Se crea:

        - un nuevo objeto de agents;
        - un nuevo Workflow;

    pero se conserva:

        - el mismo CheckpointStorage;
        - la misma autoridad monotónica de dispatch.

    La autoridad de dispatch NO pertenece al
    checkpoint y por tanto no retrocede al restaurar
    una fotografía histórica.
    """

    agents = (
        AzureWorkflowFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
            operation_dispatch_ledger=(
                operation_dispatch_ledger
            ),
        )
    )

    outputs = []
    request_info_ids = []

    replay_error = None

    try:
        async for event in workflow.run(
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
                request_info_ids.append(
                    event.request_id
                )

            elif (
                event.type
                == "output"
            ):
                outputs.append(
                    event.data
                )

    except OperationAlreadyDispatchedError as exc:
        replay_error = exc

    return (
        agents,
        outputs,
        request_info_ids,
        replay_error,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "historical_executor_id",
    [
        "azure_pre_call_security",
        "operation_start",
    ],
)
async def test_historical_pre_azure_checkpoint_cannot_replay_consumed_operation(
    historical_executor_id,
):
    """
    FASE 16 — adversarial historical replay.

    Escenario:

        HITL
          ↓ approved
        PreCallSecurity
          ↓
        OperationStart
          ↓
        Dispatch claim
          ↓
        Azure Operations
          ↓
        Registration
          ↓
        Procedure Validation
          ↓
        Transition
          ↓
        ciclo terminado

    Después de terminar correctamente se selecciona
    deliberadamente un checkpoint HISTÓRICO situado
    antes de Azure y se restaura.

    La autorización original ya fue consumida.

    Invariante requerida:

        una operación aprobada y consumida
        jamás puede volver a alcanzar Azure

    aunque el checkpoint histórico vuelva a contener
    una fotografía anterior del lifecycle.

    El bloqueo debe proceder de una autoridad
    monotónica externa al checkpoint.
    """

    dispatch_ledger = (
        InMemoryOperationDispatchLedger()
    )

    (
        storage,
        _,
        original_agents,
        original_outputs,
        original_request_info_ids,
        checkpoints,
    ) = (
        await create_completed_resumed_cycle(
            operation_dispatch_ledger=(
                dispatch_ledger
            ),
        )
    )

    #
    # --------------------------------------------------
    # Precondición:
    # operación original completa.
    # --------------------------------------------------
    #

    assert (
        original_request_info_ids
        == []
    )

    assert (
        original_agents.calls.count(
            "azure_operations"
        )
        == 1
    )

    assert (
        original_agents.calls.count(
            "procedure_validation"
        )
        == 1
    )

    assert len(
        original_outputs
    ) == 1

    #
    # El dispatch original dejó exactamente una
    # operación consumida en la autoridad externa.
    #
    assert (
        dispatch_ledger.count()
        == 1
    )

    #
    # --------------------------------------------------
    # Selección semántica del checkpoint histórico.
    # --------------------------------------------------
    #

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
    # --------------------------------------------------
    # ATAQUE:
    # restauración histórica con la MISMA autoridad
    # monotónica.
    # --------------------------------------------------
    #

    (
        replay_agents,
        replay_outputs,
        replay_request_info_ids,
        replay_error,
    ) = await restore_historical_checkpoint(
        storage=storage,
        checkpoint=(
            historical_checkpoint
        ),
        operation_dispatch_ledger=(
            dispatch_ledger
        ),
    )

    #
    # --------------------------------------------------
    # Resultado esperado: fail closed.
    # --------------------------------------------------
    #

    assert isinstance(
        replay_error,
        OperationAlreadyDispatchedError,
    )

    assert (
        "ya fue despachada"
        in str(
            replay_error
        )
    )

    #
    # No aparece un nuevo HITL.
    #
    assert (
        replay_request_info_ids
        == []
    )

    #
    # CRÍTICO:
    # el replay jamás alcanza Foundry/Azure.
    #
    assert (
        "azure_operations"
        not in replay_agents.calls
    )

    assert (
        replay_agents.calls.count(
            "azure_operations"
        )
        == 0
    )

    #
    # Al no existir segundo OperationResult tampoco
    # existe segunda Procedure Validation.
    #
    assert (
        "procedure_validation"
        not in replay_agents.calls
    )

    assert (
        replay_agents.calls.count(
            "procedure_validation"
        )
        == 0
    )

    #
    # No se genera un segundo output terminal.
    #
    assert (
        replay_outputs
        == []
    )

    #
    # La autoridad externa permanece monotónica.
    #
    assert (
        dispatch_ledger.count()
        == 1
    )