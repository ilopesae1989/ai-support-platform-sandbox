import pytest

from src.runtime.procedure.models import (
    ApprovalStatus,
    ProcedureRuntimeState,
    StepStatus,
    WorkflowStatus,
)

from src.workflows.incident_resolution.operation_dispatch_ledger import (
    InMemoryOperationDispatchLedger,
    OperationDispatchLedger,
)

from src.workflows.incident_resolution.workflow import (
    build_incident_resolution_workflow,
)

from tests.workflows.incident_resolution.test_checkpoint_hitl_resume import (
    create_checkpoint_with_pending_hitl,
)

from tests.workflows.incident_resolution.test_incident_workflow_azure_operations import (
    AzureWorkflowFakeFoundryAgents,
)


def runtime_from_checkpoint(
    checkpoint,
) -> ProcedureRuntimeState:
    assert (
        "procedure_runtime_state"
        in checkpoint.state
    )

    return (
        ProcedureRuntimeState.model_validate(
            checkpoint.state[
                "procedure_runtime_state"
            ]
        )
    )


def checkpoint_emitted_by(
    checkpoints,
    executor_id: str,
):
    """
    Selecciona por semántica del mensaje pendiente,
    no por índice ni iteration_count.
    """

    matches = [
        checkpoint
        for checkpoint in checkpoints
        if (
            set(
                checkpoint.messages.keys()
            )
            == {
                executor_id,
            }
        )
    ]

    assert len(matches) == 1, (
        f"{executor_id}: expected exactly one "
        f"checkpoint, found={len(matches)}"
    )

    return matches[0]


def assert_completed_runtime(
    outputs,
) -> ProcedureRuntimeState:
    assert len(outputs) == 1

    state = outputs[0]

    assert isinstance(
        state,
        ProcedureRuntimeState,
    )

    assert (
        state.step_status
        == StepStatus.SUCCEEDED
    )

    assert (
        state.workflow_status
        == WorkflowStatus.RUNNING
    )

    assert (
        state.approval_status
        == ApprovalStatus.APPROVED
    )

    assert (
        state.operation_result
        is not None
    )

    assert (
        state.verification_result
        is not None
    )

    return state


async def create_completed_resumed_cycle(
    operation_dispatch_ledger: (
        OperationDispatchLedger | None
    ) = None,
):
    """
    Crea:

        checkpoint HITL
            ↓ restart
        response=True
            ↓
        ciclo operacional completo

    y devuelve todos los checkpoints de esa
    rama para poder restaurar fronteras internas.

    operation_dispatch_ledger permite compartir una
    autoridad monotónica externa entre el workflow
    original y posteriores restauraciones históricas.
    """

    (
        storage,
        hitl_checkpoint,
        request_id,
    ) = (
        await create_checkpoint_with_pending_hitl()
    )

    dispatch_ledger = (
        operation_dispatch_ledger
        or InMemoryOperationDispatchLedger()
    )

    agents = (
        AzureWorkflowFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
            operation_dispatch_ledger=(
                dispatch_ledger
            ),
        )
    )

    outputs = []
    request_info_ids = []

    async for event in workflow.run(
        checkpoint_id=(
            hitl_checkpoint.checkpoint_id
        ),
        checkpoint_storage=storage,
        responses={
            request_id: True,
        },
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

    checkpoints = (
        await storage.list_checkpoints(
            workflow_name=workflow.name
        )
    )

    return (
        storage,
        hitl_checkpoint,
        agents,
        outputs,
        request_info_ids,
        checkpoints,
    )


async def restore_checkpoint(
    *,
    storage,
    checkpoint,
    operation_dispatch_ledger: (
        OperationDispatchLedger | None
    ) = None,
):
    """
    Simula restart real con nuevos agents y
    nuevo objeto Workflow.

    Si se proporciona operation_dispatch_ledger,
    la nueva instancia comparte la misma autoridad
    monotónica externa que la ejecución anterior.
    """

    dispatch_ledger = (
        operation_dispatch_ledger
        or InMemoryOperationDispatchLedger()
    )

    agents = (
        AzureWorkflowFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
            operation_dispatch_ledger=(
                dispatch_ledger
            ),
        )
    )

    outputs = []
    request_info_ids = []

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

    return (
        agents,
        outputs,
        request_info_ids,
    )


@pytest.mark.asyncio
async def test_resume_hitl_with_response_executes_exactly_one_authorized_cycle():
    """
    FASE 16.11.4

    checkpoint HITL + response aprobada debe
    continuar el ciclo ya preparado.

    No puede reconstruir la parte cognitiva
    anterior al HITL.
    """

    (
        _,
        hitl_checkpoint,
        agents,
        outputs,
        request_info_ids,
        _,
    ) = (
        await create_completed_resumed_cycle()
    )

    assert (
        request_info_ids
        == []
    )

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

    assert (
        agents.calls.count(
            "procedure_validation"
        )
        == 1
    )

    final_state = (
        assert_completed_runtime(
            outputs
        )
    )

    hitl_state = (
        runtime_from_checkpoint(
            hitl_checkpoint
        )
    )

    assert (
        final_state.approval_id
        == hitl_state.approval_id
    )

    assert (
        final_state.approval_id
        is not None
    )


@pytest.mark.asyncio
async def test_resume_after_azure_does_not_execute_azure_twice():
    """
    FASE 16.11.5

    Este checkpoint fue creado DESPUÉS de que
    AzureOperationsExecutor terminase.

    El AzureOperationResult está pendiente para
    Registration.

    Restaurarlo jamás puede volver a invocar
    Azure Operations.
    """

    (
        storage,
        _,
        _,
        _,
        _,
        checkpoints,
    ) = (
        await create_completed_resumed_cycle()
    )

    checkpoint = (
        checkpoint_emitted_by(
            checkpoints,
            "azure_operations",
        )
    )

    checkpoint_state = (
        runtime_from_checkpoint(
            checkpoint
        )
    )

    assert (
        checkpoint_state.step_status
        == StepStatus.RUNNING
    )

    assert (
        checkpoint_state.workflow_status
        == WorkflowStatus.WAITING_OPERATION
    )

    assert (
        checkpoint_state.operation_result
        is None
    )

    (
        resumed_agents,
        outputs,
        request_info_ids,
    ) = await restore_checkpoint(
        storage=storage,
        checkpoint=checkpoint,
    )

    assert (
        request_info_ids
        == []
    )

    assert (
        "azure_operations"
        not in resumed_agents.calls
    )

    assert resumed_agents.calls == [
        "procedure_validation",
    ]

    assert (
        resumed_agents.calls.count(
            "procedure_validation"
        )
        == 1
    )

    assert_completed_runtime(
        outputs
    )


@pytest.mark.asyncio
async def test_resume_after_registration_does_not_reexecute_operation():
    """
    El OperationResult ya está registrado
    autoritativamente.

    Restart debe continuar por Procedure
    Validation, nunca volver a Azure.
    """

    (
        storage,
        _,
        _,
        _,
        _,
        checkpoints,
    ) = (
        await create_completed_resumed_cycle()
    )

    checkpoint = (
        checkpoint_emitted_by(
            checkpoints,
            "operation_result_registration",
        )
    )

    checkpoint_state = (
        runtime_from_checkpoint(
            checkpoint
        )
    )

    assert (
        checkpoint_state.step_status
        == StepStatus.WAITING_VALIDATION
    )

    assert (
        checkpoint_state.workflow_status
        == WorkflowStatus.WAITING_VALIDATION
    )

    assert (
        checkpoint_state.operation_result
        is not None
    )

    assert (
        checkpoint_state.verification_result
        is None
    )

    (
        resumed_agents,
        outputs,
        request_info_ids,
    ) = await restore_checkpoint(
        storage=storage,
        checkpoint=checkpoint,
    )

    assert (
        request_info_ids
        == []
    )

    assert (
        "azure_operations"
        not in resumed_agents.calls
    )

    assert resumed_agents.calls == [
        "procedure_validation",
    ]

    assert_completed_runtime(
        outputs
    )


@pytest.mark.asyncio
async def test_resume_after_validation_does_not_revalidate_result():
    """
    Procedure Validation ya terminó antes del
    checkpoint.

    Su resultado está pendiente para
    ProcedureTransitionExecutor.

    Restart sólo puede ejecutar la transición
    determinista.

    No Azure.
    No segunda Procedure Validation.
    """

    (
        storage,
        _,
        _,
        _,
        _,
        checkpoints,
    ) = (
        await create_completed_resumed_cycle()
    )

    checkpoint = (
        checkpoint_emitted_by(
            checkpoints,
            "procedure_validation",
        )
    )

    checkpoint_state = (
        runtime_from_checkpoint(
            checkpoint
        )
    )

    assert (
        checkpoint_state.step_status
        == StepStatus.WAITING_VALIDATION
    )

    assert (
        checkpoint_state.workflow_status
        == WorkflowStatus.WAITING_VALIDATION
    )

    assert (
        checkpoint_state.operation_result
        is not None
    )

    assert (
        checkpoint_state.verification_result
        is None
    )

    (
        resumed_agents,
        outputs,
        request_info_ids,
    ) = await restore_checkpoint(
        storage=storage,
        checkpoint=checkpoint,
    )

    assert (
        request_info_ids
        == []
    )

    assert (
        resumed_agents.calls
        == []
    )

    assert (
        "azure_operations"
        not in resumed_agents.calls
    )

    assert (
        "procedure_validation"
        not in resumed_agents.calls
    )

    assert_completed_runtime(
        outputs
    )