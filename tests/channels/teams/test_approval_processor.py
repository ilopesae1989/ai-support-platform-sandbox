import pytest

from datetime import (
    timezone,
)

from src.channels.teams.approval_authorization import (
    authorize_teams_approval_invocation,
)

from src.channels.teams.approval_invocation import (
    TeamsApprovalInvocation,
    build_teams_approval_invocation,
)

from src.channels.teams.approval_processor import (
    TeamsApprovalProcessingResult,
    process_authorized_teams_approval,
)

from src.runtime.procedure.approval_channel import (
    ApprovalDecision,
)

from src.runtime.procedure.approval_resumer import (
    ApprovalResumeMismatchError,
)

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
)

from src.runtime.procedure.workflow import (
    ApprovalOutcome,
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


OTHER_CONVERSATION_ID = (
    "19:other-conversation@thread.v2"
)


async def prepare_teams_case(
    *,
    tmp_path,
    decision: ApprovalDecision,
    teams_conversation_id: str = (
        CONVERSATION_ID
    ),
):
    (
        workflow,
        _,
        approval_request,
        _,
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

    activity = (
        create_activity(
            conversation_id=(
                teams_conversation_id
            ),

            action_data={
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
        )
    )

    invocation = (
        build_teams_approval_invocation(
            activity
        )
    )

    authorized = (
        authorize_teams_approval_invocation(
            invocation=(
                invocation
            ),

            policy=(
                create_policy()
            ),
        )
    )

    return (
        workflow,
        store,
        approval_request,
        authorized,
    )


@pytest.mark.asyncio
async def test_authorized_teams_approve_resumes_real_hitl(
    tmp_path,
):
    (
        workflow,
        store,
        approval_request,
        authorized,
    ) = await prepare_teams_case(
        tmp_path=(
            tmp_path
        ),

        decision=(
            ApprovalDecision.APPROVE
        ),
    )

    processed = (
        await process_authorized_teams_approval(
            invocation=(
                authorized
            ),

            store=(
                store
            ),

            workflow=(
                workflow
            ),
        )
    )

    assert isinstance(
        processed,
        TeamsApprovalProcessingResult,
    )

    result = (
        processed.workflow_result
    )

    evidence = (
        processed.approval_evidence
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
        result.approval_id
        == approval_request.approval_id
    )

    assert (
        result.workflow_id
        == approval_request.workflow_id
    )

    assert (
        result.conversation_id
        == CONVERSATION_ID
    )

    assert (
        store.get_consumption_status(
            approval_request.approval_id
        )
        == "completed"
    )

    assert (
        evidence.workflow_id
        == approval_request.workflow_id
    )

    assert (
        evidence.approval_id
        == approval_request.approval_id
    )

    assert (
        evidence.decision
        == ApprovalDecision.APPROVE
    )

    assert (
        evidence.channel
        == "msteams"
    )

    assert (
        evidence.identity_scheme
        == "microsoft_entra_object_id"
    )

    assert (
        evidence.tenant_id
        == authorized.operator.tenant_id
    )

    assert (
        evidence.principal_id
        == authorized.operator.aad_object_id
    )

    assert (
        evidence.channel_user_id
        == authorized.operator.teams_user_id
    )

    assert (
        evidence.conversation_id
        == authorized.operator.conversation_id
    )

    assert (
        evidence.authorization_policy_id
        == authorized.policy_id
    )

    assert (
        evidence.decided_at.tzinfo
        is not None
    )

    assert (
        evidence.decided_at.utcoffset()
        == timezone.utc.utcoffset(
            evidence.decided_at
        )
    )


@pytest.mark.asyncio
async def test_authorized_teams_reject_resumes_real_hitl(
    tmp_path,
):
    (
        workflow,
        store,
        approval_request,
        authorized,
    ) = await prepare_teams_case(
        tmp_path=(
            tmp_path
        ),

        decision=(
            ApprovalDecision.REJECT
        ),
    )

    processed = (
        await process_authorized_teams_approval(
            invocation=(
                authorized
            ),

            store=(
                store
            ),

            workflow=(
                workflow
            ),
        )
    )

    assert isinstance(
        processed,
        TeamsApprovalProcessingResult,
    )

    result = (
        processed.workflow_result
    )

    evidence = (
        processed.approval_evidence
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
        == approval_request.workflow_id
    )

    assert (
        store.get_consumption_status(
            approval_request.approval_id
        )
        == "completed"
    )

    assert (
        evidence.decision
        == ApprovalDecision.REJECT
    )


@pytest.mark.asyncio
async def test_same_approval_from_other_conversation_is_blocked(
    tmp_path,
):
    (
        workflow,
        store,
        approval_request,
        authorized,
    ) = await prepare_teams_case(
        tmp_path=(
            tmp_path
        ),

        decision=(
            ApprovalDecision.APPROVE
        ),

        teams_conversation_id=(
            OTHER_CONVERSATION_ID
        ),
    )

    with pytest.raises(
        ApprovalResumeMismatchError,
        match="conversation_id",
    ):
        await process_authorized_teams_approval(
            invocation=(
                authorized
            ),

            store=(
                store
            ),

            workflow=(
                workflow
            ),
        )

    # CRÍTICO:
    #
    # El mismatch ocurre antes del claim.
    # La aprobación no se consume.
    assert (
        store.get_consumption_status(
            approval_request.approval_id
        )
        == "pending"
    )


@pytest.mark.asyncio
async def test_processor_does_not_accept_unauthorized_invocation(
    tmp_path,
):
    (
        _,
        _,
        approval_request,
        _,
    ) = await prepare_teams_case(
        tmp_path=(
            tmp_path
        ),

        decision=(
            ApprovalDecision.APPROVE
        ),
    )

    activity = (
        create_activity(
            conversation_id=(
                CONVERSATION_ID
            ),

            action_data={
                "action": (
                    "approval_decision"
                ),

                "approval_id": (
                    approval_request
                    .approval_id
                ),

                "decision": (
                    "approve"
                ),
            },
        )
    )

    invocation = (
        build_teams_approval_invocation(
            activity
        )
    )

    assert isinstance(
        invocation,
        TeamsApprovalInvocation,
    )

    with pytest.raises(
        TypeError,
        match="AuthorizedTeamsApprovalInvocation",
    ):
        await process_authorized_teams_approval(
            invocation=(
                invocation
            ),

            store=None,
            workflow=None,
        )


@pytest.mark.asyncio
async def test_approval_evidence_contains_no_operational_authority(
    tmp_path,
):
    (
        workflow,
        store,
        _,
        authorized,
    ) = await prepare_teams_case(
        tmp_path=(
            tmp_path
        ),

        decision=(
            ApprovalDecision.APPROVE
        ),
    )

    processed = (
        await process_authorized_teams_approval(
            invocation=(
                authorized
            ),

            store=(
                store
            ),

            workflow=(
                workflow
            ),
        )
    )

    payload = (
        processed
        .approval_evidence
        .model_dump(
            mode="json"
        )
    )

    assert set(
        payload
    ) == {
        "workflow_id",
        "approval_id",
        "decision",
        "channel",
        "identity_scheme",
        "tenant_id",
        "principal_id",
        "channel_user_id",
        "conversation_id",
        "authorization_policy_id",
        "display_name",
        "decided_at",
    }

    forbidden = {
        "procedure_id",
        "procedure_version",
        "step_id",
        "capability_id",
        "operation_action",
        "operation_domain",
        "operation_kind",
        "target_resource",
        "required_parameters",
        "resolved_parameters",
        "subscription_id",
        "resource_group",
        "vm_name",
        "request_id",
        "checkpoint_id",
    }

    assert (
        forbidden.isdisjoint(
            payload
        )
    )