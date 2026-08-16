from dataclasses import (
    dataclass,
)

import pytest

from microsoft_teams.api import (
    AdaptiveCardActionErrorResponse,
    AdaptiveCardActionMessageResponse,
    AdaptiveCardInvokeActivity,
)

from src.channels.teams.approval_handler import (
    TeamsApprovalHandlerDependencies,
    handle_teams_approval_action,
)

from src.runtime.procedure.approval_channel import (
    ApprovalDecision,
)

from src.runtime.procedure.workflow import (
    build_procedure_approval_workflow,
)

from tests.channels.teams.test_activity_identity import (
    CONVERSATION_ID,
    create_activity,
)

from tests.channels.teams.test_approval_authorization import (
    create_policy,
)

from tests.runtime.procedure.test_approval_resumer import (
    prepare_pending_approval,
)


@dataclass
class FakeActivityContext:
    activity: AdaptiveCardInvokeActivity


async def prepare_handler_case(
    *,
    tmp_path,
    decision: ApprovalDecision,
    aad_object_id: str | None = None,
):
    (
        _,
        _,
        approval_request,
        checkpoint_dir,
        store,
    ) = await prepare_pending_approval(
        tmp_path=(
            tmp_path
        ),

        decision=(
            decision
        ),

        conversation_id=(
            CONVERSATION_ID
        ),
    )

    activity_kwargs = {
        "conversation_id": (
            CONVERSATION_ID
        ),

        "action_data": {
            "action": (
                "approval_decision"
            ),

            "approval_id": (
                approval_request
                .approval_id
            ),

            "decision": (
                decision.value
            ),
        },
    }

    if (
        aad_object_id
        is not None
    ):
        activity_kwargs[
            "aad_object_id"
        ] = aad_object_id

    activity = (
        create_activity(
            **activity_kwargs
        )
    )

    dependencies = (
        TeamsApprovalHandlerDependencies(
            policy=(
                create_policy()
            ),

            store=(
                store
            ),

            workflow_factory=(
                lambda: (
                    build_procedure_approval_workflow(
                        str(
                            checkpoint_dir
                        )
                    )
                )
            ),
        )
    )

    return (
        FakeActivityContext(
            activity=(
                activity
            )
        ),

        dependencies,

        approval_request,

        store,
    )


@pytest.mark.asyncio
async def test_real_teams_handler_approves_pending_hitl(
    tmp_path,
):
    (
        ctx,
        dependencies,
        approval_request,
        store,
    ) = await prepare_handler_case(
        tmp_path=(
            tmp_path
        ),

        decision=(
            ApprovalDecision.APPROVE
        ),
    )

    response = (
        await handle_teams_approval_action(
            ctx=ctx,
            dependencies=dependencies,
        )
    )

    assert isinstance(
        response,
        AdaptiveCardActionMessageResponse,
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        "Aprobación registrada"
        in response.value
    )

    assert (
        store.get_consumption_status(
            approval_request.approval_id
        )
        == "completed"
    )


@pytest.mark.asyncio
async def test_real_teams_handler_rejects_pending_hitl(
    tmp_path,
):
    (
        ctx,
        dependencies,
        approval_request,
        store,
    ) = await prepare_handler_case(
        tmp_path=(
            tmp_path
        ),

        decision=(
            ApprovalDecision.REJECT
        ),
    )

    response = (
        await handle_teams_approval_action(
            ctx=ctx,
            dependencies=dependencies,
        )
    )

    assert isinstance(
        response,
        AdaptiveCardActionMessageResponse,
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        "Rechazo registrado"
        in response.value
    )

    assert (
        store.get_consumption_status(
            approval_request.approval_id
        )
        == "completed"
    )


@pytest.mark.asyncio
async def test_unauthorized_operator_fails_closed_before_claim(
    tmp_path,
):
    (
        ctx,
        dependencies,
        approval_request,
        store,
    ) = await prepare_handler_case(
        tmp_path=(
            tmp_path
        ),

        decision=(
            ApprovalDecision.APPROVE
        ),

        aad_object_id=(
            "22222222-2222-4222-"
            "8222-222222222222"
        ),
    )

    response = (
        await handle_teams_approval_action(
            ctx=ctx,
            dependencies=dependencies,
        )
    )

    assert isinstance(
        response,
        AdaptiveCardActionErrorResponse,
    )

    assert (
        response.status_code
        == 400
    )

    assert (
        store.get_consumption_status(
            approval_request.approval_id
        )
        == "pending"
    )


@pytest.mark.asyncio
async def test_second_teams_submit_is_rejected_as_replay(
    tmp_path,
):
    (
        ctx,
        dependencies,
        approval_request,
        store,
    ) = await prepare_handler_case(
        tmp_path=(
            tmp_path
        ),

        decision=(
            ApprovalDecision.APPROVE
        ),
    )

    first = (
        await handle_teams_approval_action(
            ctx=ctx,
            dependencies=dependencies,
        )
    )

    assert isinstance(
        first,
        AdaptiveCardActionMessageResponse,
    )

    assert (
        first.status_code
        == 200
    )

    second = (
        await handle_teams_approval_action(
            ctx=ctx,
            dependencies=dependencies,
        )
    )

    assert isinstance(
        second,
        AdaptiveCardActionErrorResponse,
    )

    assert (
        second.status_code
        == 400
    )

    assert (
        store.get_consumption_status(
            approval_request.approval_id
        )
        == "completed"
    )