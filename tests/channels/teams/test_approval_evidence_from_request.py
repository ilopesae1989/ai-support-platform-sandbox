from dataclasses import replace

import pytest

import src.channels.teams.approval_evidence as approval_evidence

from src.channels.teams.approval_authorization import (
    AuthorizedTeamsApprovalInvocation,
)

from src.channels.teams.operator_identity import (
    TeamsOperatorIdentity,
)

from src.runtime.procedure.approval_channel import (
    ApprovalChannelAction,
    ApprovalDecision,
)

from tests.channels.teams.test_approval_card import (
    create_request,
)


TENANT_ID = (
    "3048dc87-43f0-4100-"
    "9acb-ae1971c79395"
)

AAD_OBJECT_ID = (
    "11111111-2222-3333-"
    "4444-555555555555"
)

TEAMS_USER_ID = "29:teams-user-phase18"
CONVERSATION_ID = "a:test-approval-conversation"
POLICY_ID = "teams-hitl-sandbox-v1"


def create_restored_request():
    return replace(
        create_request(),
        conversation_id=CONVERSATION_ID,
    )


def create_authorized_invocation(
    request,
    *,
    decision=ApprovalDecision.APPROVE,
):
    return AuthorizedTeamsApprovalInvocation(
        policy_id=POLICY_ID,
        operator=TeamsOperatorIdentity(
            tenant_id=TENANT_ID,
            aad_object_id=AAD_OBJECT_ID,
            teams_user_id=TEAMS_USER_ID,
            conversation_id=CONVERSATION_ID,
            display_name="Phase 18 Operator",
        ),
        action=ApprovalChannelAction(
            approval_id=request.approval_id,
            decision=decision,
        ),
    )


def test_builds_evidence_from_restored_approval_request():
    request = create_restored_request()
    invocation = create_authorized_invocation(request)

    evidence = (
        approval_evidence
        .build_teams_approval_evidence_from_request(
            invocation=invocation,
            request=request,
        )
    )

    assert isinstance(
        evidence,
        approval_evidence.ApprovalDecisionEvidence,
    )

    assert evidence.workflow_id == request.workflow_id
    assert evidence.approval_id == request.approval_id
    assert evidence.decision == ApprovalDecision.APPROVE
    assert evidence.channel == "msteams"
    assert evidence.identity_scheme == "microsoft_entra_object_id"
    assert evidence.tenant_id == TENANT_ID
    assert evidence.principal_id == AAD_OBJECT_ID
    assert evidence.channel_user_id == TEAMS_USER_ID
    assert evidence.conversation_id == CONVERSATION_ID
    assert evidence.authorization_policy_id == POLICY_ID
    assert evidence.decided_at.tzinfo is not None


def test_approval_id_mismatch_fails_closed():
    request = create_restored_request()
    invocation = create_authorized_invocation(request)

    tampered_request = replace(
        request,
        approval_id="apr-different",
    )

    with pytest.raises(
        approval_evidence.TeamsApprovalEvidenceError
    ):
        approval_evidence.build_teams_approval_evidence_from_request(
            invocation=invocation,
            request=tampered_request,
        )


def test_conversation_id_mismatch_fails_closed():
    request = create_restored_request()
    invocation = create_authorized_invocation(request)

    tampered_request = replace(
        request,
        conversation_id="a:other-conversation",
    )

    with pytest.raises(
        approval_evidence.TeamsApprovalEvidenceError
    ):
        approval_evidence.build_teams_approval_evidence_from_request(
            invocation=invocation,
            request=tampered_request,
        )


def test_missing_request_conversation_fails_closed():
    request = create_restored_request()
    invocation = create_authorized_invocation(request)

    invalid_request = replace(
        request,
        conversation_id=None,
    )

    with pytest.raises(
        approval_evidence.TeamsApprovalEvidenceError
    ):
        approval_evidence.build_teams_approval_evidence_from_request(
            invocation=invocation,
            request=invalid_request,
        )
