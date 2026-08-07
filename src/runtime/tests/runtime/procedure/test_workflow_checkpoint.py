import pytest

from agent_framework import FileCheckpointStorage

from src.runtime.procedure.models import (
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
)
from src.runtime.procedure.workflow import (
    ApprovalOutcome,
    build_procedure_approval_workflow,
)


def create_state() -> ProcedureRuntimeState:
    return ProcedureRuntimeState(
        workflow_id="wf-checkpoint-001",
        conversation_id="conv-checkpoint-001",
        alert_id="ALT-SQL-AG-001",
        procedure=ProcedureReference(
            id="NTTSY-PRO-020",
            name="Alertas SQL Server",
            version="v1.1",
        ),
        total_steps=5,
        current_step=1,
        step=ProcedureStep(
            id="1",
            description=(
                "Comprobar el estado actual de "
                "la réplica de Always On."
            ),
            step_type="validation",
            operation_domain="database",
            operation_kind=OperationKind.READ,
            target_resource="SQLPROD01",
        ),
    )


@pytest.mark.asyncio
async def test_pending_approval_survives_checkpoint(
    tmp_path,
):
    checkpoint_dir = tmp_path / "checkpoints"

    #
    # Primera instancia del workflow.
    #
    workflow_a = build_procedure_approval_workflow(
        str(checkpoint_dir)
    )

    state = create_state()

    request_id = None

    async for event in workflow_a.run(
        state,
        stream=True,
    ):
        if event.type == "request_info":
            request_id = event.request_id

    assert request_id is not None

    #
    # Recuperamos el checkpoint creado automáticamente.
    #
    storage = FileCheckpointStorage(
        str(checkpoint_dir)
    )

    checkpoints = await storage.list_checkpoints()

    assert len(checkpoints) > 0

    latest_checkpoint = sorted(
        checkpoints,
        key=lambda checkpoint: checkpoint.timestamp,
        reverse=True,
    )[0]

    #
    # Simulamos un proceso completamente nuevo.
    #
    workflow_b = build_procedure_approval_workflow(
        str(checkpoint_dir)
    )

    #
    # Primero restauramos el checkpoint.
    #
    restored_request_id = None

    async for event in workflow_b.run(
        checkpoint_id=latest_checkpoint.checkpoint_id,
        stream=True,
    ):
        if event.type == "request_info":
            restored_request_id = event.request_id

    assert restored_request_id is not None
    assert restored_request_id == request_id

    #
    # Después enviamos la aprobación.
    #
    outputs = []

    async for event in workflow_b.run(
        responses={
            restored_request_id: True,
        },
        stream=True,
    ):
        if event.type == "output":
            outputs.append(event.data)

    assert len(outputs) == 1

    result = outputs[0]

    assert isinstance(
        result,
        ApprovalOutcome,
    )

    assert result.workflow_id == "wf-checkpoint-001"
    assert result.approved is True
    assert result.status == "running"