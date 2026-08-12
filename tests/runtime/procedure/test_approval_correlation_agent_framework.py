import pytest

from agent_framework import (
    FileCheckpointStorage,
)

from src.runtime.procedure.approval_correlation import (
    build_pending_approval_correlation,
)

from src.runtime.procedure.approval_store import (
    SqlitePendingApprovalStore,
)

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
)

from src.runtime.procedure.workflow import (
    ApprovalRequest,
    build_procedure_approval_workflow,
)

from tests.runtime.procedure.test_workflow_checkpoint import (
    ALLOWED_CHECKPOINT_TYPES,
    WORKFLOW_ID,
    create_state,
)


@pytest.mark.asyncio
async def test_real_agent_framework_hitl_can_be_correlated_and_resumed(
    tmp_path,
):
    """
    FASE 18.1.3

    Demuestra la unión real entre:

        approval_id
            ↓
        Agent Framework request_id
            ↓
        checkpoint_id
            ↓
        restore
            ↓
        response
            ↓
        ApprovedProcedureStep

    No utiliza IDs sintéticos para request_id ni
    checkpoint_id.

    Ambos deben proceder realmente de Agent Framework.
    """

    checkpoint_dir = (
        tmp_path
        / "checkpoints"
    )

    # --------------------------------------------------
    # 1. Crear workflow con checkpointing real
    # --------------------------------------------------

    workflow_a = (
        build_procedure_approval_workflow(
            str(checkpoint_dir)
        )
    )

    state = (
        create_state()
    )

    request_event = None

    async for event in workflow_a.run(
        state,
        stream=True,
    ):
        if event.type == "request_info":
            assert (
                request_event
                is None
            )

            request_event = (
                event
            )

    assert (
        request_event
        is not None
    )

    assert (
        request_event.request_id
    )

    assert isinstance(
        request_event.data,
        ApprovalRequest,
    )

    approval_request = (
        request_event.data
    )

    assert (
        approval_request.workflow_id
        == WORKFLOW_ID
    )

    assert (
        approval_request.approval_id
    )

    # --------------------------------------------------
    # 2. Recuperar checkpoint REAL
    # --------------------------------------------------

    storage = FileCheckpointStorage(
        str(checkpoint_dir),

        allowed_checkpoint_types=(
            ALLOWED_CHECKPOINT_TYPES
        ),
    )

    checkpoints = (
        await storage.list_checkpoints(
            workflow_name=(
                "procedure-runtime"
            )
        )
    )

    assert checkpoints

    latest_checkpoint = sorted(
        checkpoints,

        key=lambda checkpoint:
            checkpoint.timestamp,

        reverse=True,
    )[0]

    assert (
        latest_checkpoint.checkpoint_id
    )

    # --------------------------------------------------
    # 3. Crear correlación desde datos reales
    # --------------------------------------------------

    correlation = (
        build_pending_approval_correlation(
            request=(
                approval_request
            ),

            request_id=(
                request_event.request_id
            ),

            checkpoint_id=(
                latest_checkpoint.checkpoint_id
            ),
        )
    )

    assert (
        correlation.approval_id
        == approval_request.approval_id
    )

    assert (
        correlation.workflow_id
        == WORKFLOW_ID
    )

    assert (
        correlation.request_id
        == request_event.request_id
    )

    assert (
        correlation.checkpoint_id
        == latest_checkpoint.checkpoint_id
    )

    # --------------------------------------------------
    # 4. Registrar como haría posteriormente
    #    el Pending Approval Store
    # --------------------------------------------------

    pending_approval_database = (
        tmp_path
        / "pending-approvals.db"
    )

    store_a = (
        SqlitePendingApprovalStore(
            pending_approval_database
        )
    )

    store_a.register(
        correlation
    )

    # Nueva instancia:
    # simula el worker que posteriormente
    # recibe la acción desde Teams.
    store_b = (
        SqlitePendingApprovalStore(
            pending_approval_database
        )
    )

    # Simula lo único que traerá Teams:
    #
    #     approval_id
    #     decision
    #
    resolved = (
        store_b.get_by_approval_id(
            approval_request.approval_id
        )
    )

    assert (
        resolved
        == correlation
    )

    # --------------------------------------------------
    # 5. Simular otro proceso / worker
    # --------------------------------------------------

    workflow_b = (
        build_procedure_approval_workflow(
            str(checkpoint_dir)
        )
    )

    restored_event = None

    async for event in workflow_b.run(
        checkpoint_id=(
            resolved.checkpoint_id
        ),

        stream=True,
    ):
        if event.type == "request_info":
            assert (
                restored_event
                is None
            )

            restored_event = (
                event
            )

    assert (
        restored_event
        is not None
    )

    # --------------------------------------------------
    # 6. La correlación técnica debe seguir siendo
    #    exactamente la misma
    # --------------------------------------------------

    assert (
        restored_event.request_id
        == resolved.request_id
    )

    assert isinstance(
        restored_event.data,
        ApprovalRequest,
    )

    assert (
        restored_event.data
        == approval_request
    )

    assert (
        restored_event.data.approval_id
        == resolved.approval_id
    )

    assert (
        restored_event.data.workflow_id
        == resolved.workflow_id
    )

    # --------------------------------------------------
    # 7. Reanudar exclusivamente mediante request_id
    #    recuperado de la correlación backend
    # --------------------------------------------------

    outputs = []

    async for event in workflow_b.run(
        responses={
            resolved.request_id:
                True,
        },

        stream=True,
    ):
        if event.type == "output":
            outputs.append(
                event.data
            )

    assert (
        len(outputs)
        == 1
    )

    result = (
        outputs[0]
    )

    assert isinstance(
        result,
        ApprovedProcedureStep,
    )

    assert (
        result.approved
        is True
    )

    assert (
        result.workflow_id
        == resolved.workflow_id
    )

    assert (
        result.approval_id
        == resolved.approval_id
    )