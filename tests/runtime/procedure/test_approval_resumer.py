import pytest

from agent_framework import (
    FileCheckpointStorage,
)

from src.runtime.procedure.approval_channel import (
    ApprovalChannelAction,
    ApprovalDecision,
)

from src.runtime.procedure.approval_correlation import (
    build_pending_approval_correlation,
)

from src.runtime.procedure.approval_resolution import (
    ApprovalResumeInstruction,
    resolve_approval_channel_action,
)

from src.runtime.procedure.approval_resumer import (
    ApprovalResumeMismatchError,
    resume_approval_workflow,
)

from src.runtime.procedure.approval_store import (
    ApprovalAlreadyConsumedError,
    SqlitePendingApprovalStore,
)

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
)

from src.runtime.procedure.workflow import (
    ApprovalOutcome,
    ApprovalRequest,
    build_procedure_approval_workflow,
)

from tests.runtime.procedure.test_workflow_checkpoint import (
    ALLOWED_CHECKPOINT_TYPES,
    WORKFLOW_ID,
    create_state,
)


async def prepare_pending_approval(
    *,
    tmp_path,
    decision: ApprovalDecision,
    conversation_id: str | None = None,
):
    """
    Genera realmente:

        RequestInfoEvent
        request_id
        checkpoint_id
        ApprovalRequest

    y después simula otro worker recuperando
    exclusivamente approval_id desde el canal.
    """

    checkpoint_dir = (
        tmp_path
        / "checkpoints"
    )

    workflow_a = (
        build_procedure_approval_workflow(
            str(checkpoint_dir)
        )
    )

    request_event = None

    state = (
        create_state()
    )

    if (
        conversation_id
        is not None
    ):
        state = (
            state.model_copy(
                update={
                    "conversation_id": (
                        conversation_id
                    ),
                }
            )
        )

    async for event in workflow_a.run(
        state,
        stream=True,
    ):
        if (
            event.type
            == "request_info"
        ):
            request_event = (
                event
            )

    assert (
        request_event
        is not None
    )

    assert isinstance(
        request_event.data,
        ApprovalRequest,
    )

    approval_request = (
        request_event.data
    )

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

    correlation = (
        build_pending_approval_correlation(
            request=(
                approval_request
            ),

            request_id=(
                request_event.request_id
            ),

            checkpoint_id=(
                latest_checkpoint
                .checkpoint_id
            ),
        )
    )

    pending_database = (
        tmp_path
        / "pending-approvals.db"
    )

    store_a = (
        SqlitePendingApprovalStore(
            pending_database
        )
    )

    store_a.register(
        correlation
    )

    # Nuevo store:
    # simula el proceso que recibe posteriormente
    # la interacción del canal.
    store_b = (
        SqlitePendingApprovalStore(
            pending_database
        )
    )

    action = (
        ApprovalChannelAction(
            approval_id=(
                approval_request
                .approval_id
            ),

            decision=(
                decision
            ),
        )
    )

    instruction = (
        resolve_approval_channel_action(
            action=action,
            store=store_b,
        )
    )

    # Nuevo workflow:
    # simula otro worker/proceso.
    workflow_b = (
        build_procedure_approval_workflow(
            str(checkpoint_dir)
        )
    )

    return (
        workflow_b,
        instruction,
        approval_request,
        checkpoint_dir,
        store_b,
    )


@pytest.mark.asyncio
async def test_approved_channel_action_resumes_real_workflow(
    tmp_path,
):
    (
        workflow,
        instruction,
        approval_request,
        _,
        store,
    ) = await prepare_pending_approval(
        tmp_path=tmp_path,
        decision=(
            ApprovalDecision.APPROVE
        ),
    )

    result = (
        await resume_approval_workflow(
            workflow=workflow,
            instruction=instruction,
            store=store,
        )
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
        == instruction.workflow_id
    )

    assert (
        result.approval_id
        == instruction.approval_id
    )

    assert (
        result.workflow_id
        == approval_request.workflow_id
    )

    assert (
        result.approval_id
        == approval_request.approval_id
    )


@pytest.mark.asyncio
async def test_rejected_channel_action_resumes_real_workflow(
    tmp_path,
):
    (
        workflow,
        instruction,
        _,
        _,
        store,
    ) = await prepare_pending_approval(
        tmp_path=tmp_path,
        decision=(
            ApprovalDecision.REJECT
        ),
    )

    result = (
        await resume_approval_workflow(
            workflow=workflow,
            instruction=instruction,
            store=store,
        )
    )

    assert isinstance(
        result,
        ApprovalOutcome,
    )

    assert (
        result.approved
        is False
    )

    assert (
        result.workflow_id
        == instruction.workflow_id
    )


@pytest.mark.asyncio
async def test_tampered_request_id_is_blocked_before_response(
    tmp_path,
):
    (
        workflow,
        instruction,
        _,
        checkpoint_dir,
        store,
    ) = await prepare_pending_approval(
        tmp_path=tmp_path,
        decision=(
            ApprovalDecision.APPROVE
        ),
    )

    tampered = (
        ApprovalResumeInstruction(
            approval_id=(
                instruction.approval_id
            ),

            workflow_id=(
                instruction.workflow_id
            ),

            request_id=(
                "req-attacker"
            ),

            checkpoint_id=(
                instruction.checkpoint_id
            ),

            approved=True,
        )
    )

    with pytest.raises(
        ApprovalResumeMismatchError,
        match="request_id",
    ):
        await resume_approval_workflow(
            workflow=workflow,
            instruction=tampered,
            store=store,
        )

    # --------------------------------------------------
    # Demostrar que NO se respondió al HITL.
    #
    # Otro workflow puede restaurar el mismo
    # checkpoint y la solicitud sigue pendiente.
    # --------------------------------------------------

    verification_workflow = (
        build_procedure_approval_workflow(
            str(checkpoint_dir)
        )
    )

    pending_request_ids = []

    async for event in verification_workflow.run(
        checkpoint_id=(
            instruction.checkpoint_id
        ),

        stream=True,
    ):
        if (
            event.type
            == "request_info"
        ):
            pending_request_ids.append(
                event.request_id
            )

    assert (
        pending_request_ids
        == [
            instruction.request_id
        ]
    )


@pytest.mark.asyncio
async def test_tampered_approval_id_is_blocked_before_response(
    tmp_path,
):
    (
        workflow,
        instruction,
        _,
        _,
        store,
    ) = await prepare_pending_approval(
        tmp_path=tmp_path,
        decision=(
            ApprovalDecision.APPROVE
        ),
    )

    tampered = (
        ApprovalResumeInstruction(
            approval_id=(
                "apr-attacker"
            ),

            workflow_id=(
                instruction.workflow_id
            ),

            request_id=(
                instruction.request_id
            ),

            checkpoint_id=(
                instruction.checkpoint_id
            ),

            approved=True,
        )
    )

    with pytest.raises(
        ApprovalResumeMismatchError,
        match="approval_id",
    ):
        await resume_approval_workflow(
            workflow=workflow,
            instruction=tampered,
            store=store,
        )


@pytest.mark.asyncio
async def test_tampered_workflow_id_is_blocked_before_response(
    tmp_path,
):
    (
        workflow,
        instruction,
        _,
        _,
        store,
    ) = await prepare_pending_approval(
        tmp_path=tmp_path,
        decision=(
            ApprovalDecision.APPROVE
        ),
    )

    tampered = (
        ApprovalResumeInstruction(
            approval_id=(
                instruction.approval_id
            ),

            workflow_id=(
                "wf-attacker"
            ),

            request_id=(
                instruction.request_id
            ),

            checkpoint_id=(
                instruction.checkpoint_id
            ),

            approved=True,
        )
    )

    with pytest.raises(
        ApprovalResumeMismatchError,
        match="workflow_id",
    ):
        await resume_approval_workflow(
            workflow=workflow,
            instruction=tampered,
            store=store,
        )


@pytest.mark.asyncio
async def test_same_approval_cannot_resume_twice(
    tmp_path,
):
    (
        workflow,
        instruction,
        _,
        checkpoint_dir,
        store,
    ) = await prepare_pending_approval(
        tmp_path=tmp_path,
        decision=(
            ApprovalDecision.APPROVE
        ),
    )

    first = (
        await resume_approval_workflow(
            workflow=workflow,
            instruction=instruction,
            store=store,
        )
    )

    assert isinstance(
        first,
        ApprovedProcedureStep,
    )

    assert (
        store.get_consumption_status(
            instruction.approval_id
        )
        == "completed"
    )

    # Nuevo workflow:
    # simula un segundo callback de Teams.
    replay_workflow = (
        build_procedure_approval_workflow(
            str(checkpoint_dir)
        )
    )

    replay_store = (
        SqlitePendingApprovalStore(
            tmp_path
            / "pending-approvals.db"
        )
    )

    with pytest.raises(
        ApprovalAlreadyConsumedError,
    ):
        await resume_approval_workflow(
            workflow=replay_workflow,
            instruction=instruction,
            store=replay_store,
        )