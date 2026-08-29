from types import (
    SimpleNamespace,
)

import pytest

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


APPROVAL_ID = "apr-phase18-incident-001"
WORKFLOW_ID = "wf-phase18-incident-001"

REQUEST_ID = "req-phase18-incident-001"
CHECKPOINT_ID = "cp-phase18-incident-001"

TENANT_ID = (
    "3048dc87-43f0-4100-"
    "9acb-ae1971c79395"
)

AAD_OBJECT_ID = (
    "11111111-2222-3333-"
    "4444-555555555555"
)

TEAMS_USER_ID = (
    "29:teams-user-phase18"
)

CONVERSATION_ID = (
    "19:phase18-incident@thread.v2"
)

POLICY_ID = (
    "teams-hitl-sandbox-v1"
)


def create_invocation(
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
            approval_id=APPROVAL_ID,
            decision=decision,
        ),
    )


def create_instruction(
    *,
    approved=True,
):
    return SimpleNamespace(
        approval_id=APPROVAL_ID,
        workflow_id=WORKFLOW_ID,

        request_id=REQUEST_ID,
        checkpoint_id=CHECKPOINT_ID,

        approved=approved,
    )


def create_claimed():
    return SimpleNamespace(
        approval_id=APPROVAL_ID,
        workflow_id=WORKFLOW_ID,

        request_id=REQUEST_ID,
        checkpoint_id=CHECKPOINT_ID,
    )


class FakeStore:
    def __init__(
        self,
        *,
        claimed=None,
    ):
        self.claimed = (
            claimed
            if claimed is not None
            else create_claimed()
        )

        self.claim_calls = []
        self.complete_calls = []

    def claim(
        self,
        *,
        approval_id,
        approved,
    ):
        self.claim_calls.append(
            (
                approval_id,
                approved,
            )
        )

        return self.claimed

    def complete(
        self,
        approval_id,
    ):
        self.complete_calls.append(
            approval_id
        )


class FakeWorkflow:
    def __init__(
        self,
        events,
    ):
        self.events = list(events)
        self.run_calls = []

    async def run(
        self,
        **kwargs,
    ):
        self.run_calls.append(
            kwargs
        )

        for event in self.events:
            yield event


@pytest.mark.asyncio
async def test_approved_incident_resumes_exactly_once_and_completes(
    monkeypatch,
):
    import src.channels.teams.incident_approval_processor as processor

    invocation = create_invocation()

    instruction = create_instruction(
        approved=True
    )

    restored_request = object()
    final_result = object()
    approval_evidence = object()

    checkpoint_storage = object()

    workflow = FakeWorkflow(
        [
            SimpleNamespace(
                type="output",
                data=final_result,
            )
        ]
    )

    store = FakeStore()

    sequence = []

    def fake_resolve(
        *,
        action,
        store,
    ):
        sequence.append(
            "resolve"
        )

        assert action is invocation.action

        return instruction

    async def fake_restore(
        *,
        workflow,
        instruction,
        expected_conversation_id,
        checkpoint_storage,
    ):
        sequence.append(
            "restore"
        )

        assert workflow is expected_workflow
        assert instruction is expected_instruction

        assert (
            expected_conversation_id
            == CONVERSATION_ID
        )

        assert (
            checkpoint_storage
            is expected_checkpoint_storage
        )

        return restored_request

    def fake_build_evidence(
        *,
        invocation,
        request,
    ):
        sequence.append(
            "evidence"
        )

        assert invocation is expected_invocation
        assert request is restored_request

        return approval_evidence

    expected_workflow = workflow
    expected_instruction = instruction
    expected_checkpoint_storage = checkpoint_storage
    expected_invocation = invocation

    monkeypatch.setattr(
        processor,
        "resolve_approval_channel_action",
        fake_resolve,
        raising=False,
    )

    monkeypatch.setattr(
        processor,
        "restore_and_verify_pending_request",
        fake_restore,
        raising=False,
    )

    monkeypatch.setattr(
        processor,
        "build_teams_approval_evidence_from_request",
        fake_build_evidence,
        raising=False,
    )

    result = await (
        processor
        .process_authorized_teams_incident_approval(
            invocation=invocation,
            store=store,
            workflow=workflow,
            checkpoint_storage=(
                checkpoint_storage
            ),
        )
    )

    assert (
        result.workflow_result
        is final_result
    )

    assert (
        result.approval_evidence
        is approval_evidence
    )

    assert store.claim_calls == [
        (
            APPROVAL_ID,
            True,
        )
    ]

    assert workflow.run_calls == [
        {
            "responses": {
                REQUEST_ID: True,
            },
            "checkpoint_storage":
                checkpoint_storage,
            "stream":
                True,
        }
    ]

    assert store.complete_calls == [
        APPROVAL_ID
    ]

    assert sequence == [
        "resolve",
        "restore",
        "evidence",
    ]


@pytest.mark.asyncio
async def test_claim_identity_mismatch_fails_before_response(
    monkeypatch,
):
    import src.channels.teams.incident_approval_processor as processor

    invocation = create_invocation()

    instruction = create_instruction(
        approved=True
    )

    checkpoint_storage = object()

    mismatched_claim = SimpleNamespace(
        approval_id=APPROVAL_ID,
        workflow_id="wf-attacker",

        request_id=REQUEST_ID,
        checkpoint_id=CHECKPOINT_ID,
    )

    store = FakeStore(
        claimed=mismatched_claim
    )

    workflow = FakeWorkflow(
        []
    )

    async def fake_restore(
        **kwargs,
    ):
        return object()

    monkeypatch.setattr(
        processor,
        "resolve_approval_channel_action",
        lambda **kwargs: instruction,
        raising=False,
    )

    monkeypatch.setattr(
        processor,
        "restore_and_verify_pending_request",
        fake_restore,
        raising=False,
    )

    with pytest.raises(
        processor
        .IncidentApprovalProcessingError
    ):
        await (
            processor
            .process_authorized_teams_incident_approval(
                invocation=invocation,
                store=store,
                workflow=workflow,
                checkpoint_storage=(
                    checkpoint_storage
                ),
            )
        )

    assert workflow.run_calls == []

    assert store.complete_calls == []


@pytest.mark.asyncio
async def test_new_request_after_response_fails_closed_without_complete(
    monkeypatch,
):
    import src.channels.teams.incident_approval_processor as processor

    invocation = create_invocation()

    instruction = create_instruction(
        approved=True
    )

    checkpoint_storage = object()

    workflow = FakeWorkflow(
        [
            SimpleNamespace(
                type="request_info",
                request_id="unexpected-request",
                data=object(),
            )
        ]
    )

    store = FakeStore()

    evidence_calls = []

    async def fake_restore(
        **kwargs,
    ):
        return object()

    def fake_evidence(
        **kwargs,
    ):
        evidence_calls.append(
            kwargs
        )

        return object()

    monkeypatch.setattr(
        processor,
        "resolve_approval_channel_action",
        lambda **kwargs: instruction,
        raising=False,
    )

    monkeypatch.setattr(
        processor,
        "restore_and_verify_pending_request",
        fake_restore,
        raising=False,
    )

    monkeypatch.setattr(
        processor,
        "build_teams_approval_evidence_from_request",
        fake_evidence,
        raising=False,
    )

    with pytest.raises(
        processor
        .IncidentApprovalProcessingError
    ):
        await (
            processor
            .process_authorized_teams_incident_approval(
                invocation=invocation,
                store=store,
                workflow=workflow,
                checkpoint_storage=(
                    checkpoint_storage
                ),
            )
        )

    assert store.claim_calls == [
        (
            APPROVAL_ID,
            True,
        )
    ]

    assert evidence_calls == []

    assert store.complete_calls == []
