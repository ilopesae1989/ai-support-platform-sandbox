from __future__ import annotations

import pytest

from src.channels.teams.approval_authorization import (
    AuthorizedTeamsApprovalInvocation,
)

from src.channels.teams.incident_continuation_store import (
    IncidentContinuationClaimError,
    IncidentContinuationStatus,
    SqliteIncidentContinuationStore,
)

from src.channels.teams.operator_identity import (
    TeamsOperatorIdentity,
)

from src.runtime.procedure.approval_channel import (
    ApprovalChannelAction,
    ApprovalDecision,
)

from src.runtime.procedure.approval_correlation import (
    PendingApprovalCorrelation,
)

from src.runtime.procedure.approval_store import (
    SqlitePendingApprovalStore,
)


APPROVAL_ID = "apr-recovery-433"

WORKFLOW_ID = "wf-recovery-433"

REQUEST_ID = "req-recovery-433"

CHECKPOINT_ID = "cp-recovery-433"


def _invocation(
    decision=ApprovalDecision.APPROVE,
):
    return AuthorizedTeamsApprovalInvocation(
        policy_id="teams-hitl-sandbox-v1",

        operator=TeamsOperatorIdentity(
            tenant_id="tenant-recovery-433",
            aad_object_id="aad-recovery-433",
            teams_user_id="teams-recovery-433",
            conversation_id="conversation-recovery-433",
            display_name="Recovery Operator",
        ),

        action=ApprovalChannelAction(
            approval_id=APPROVAL_ID,
            decision=decision,
        ),
    )


def _stores(
    tmp_path,
):
    continuation = (
        SqliteIncidentContinuationStore(
            tmp_path / "continuation.db"
        )
    )

    approval = (
        SqlitePendingApprovalStore(
            tmp_path / "approval.db"
        )
    )

    approval.register(
        PendingApprovalCorrelation(
            approval_id=APPROVAL_ID,
            workflow_id=WORKFLOW_ID,
            request_id=REQUEST_ID,
            checkpoint_id=CHECKPOINT_ID,
        )
    )

    continuation.enqueue(
        _invocation()
    )

    return (
        continuation,
        approval,
    )


def test_claimed_before_approval_can_return_to_pending(
    tmp_path,
):
    continuation, approval = (
        _stores(
            tmp_path
        )
    )

    claimed = (
        continuation.claim_next(
            worker_id="worker-old"
        )
    )

    assert claimed is not None

    assert (
        claimed.status
        == IncidentContinuationStatus.CLAIMED
    )

    recovered = (
        continuation
        .recover_claimed_before_approval(
            approval_id=APPROVAL_ID,
            worker_id="worker-old",
            approval_store=approval,
        )
    )

    assert (
        recovered.status
        == IncidentContinuationStatus.PENDING
    )

    assert recovered.claimed_by is None

    assert recovered.attempt_count == 1

    reclaimed = (
        continuation.claim_next(
            worker_id="worker-new"
        )
    )

    assert reclaimed is not None

    assert (
        reclaimed.status
        == IncidentContinuationStatus.CLAIMED
    )

    assert reclaimed.claimed_by == "worker-new"

    assert reclaimed.attempt_count == 2


@pytest.mark.parametrize(
    "approved",
    [
        True,
        False,
    ],
)
def test_claimed_approval_blocks_recovery(
    tmp_path,
    approved,
):
    continuation, approval = (
        _stores(
            tmp_path
        )
    )

    claimed = continuation.claim_next(
        worker_id="worker-old"
    )

    assert claimed is not None

    approval.claim(
        approval_id=APPROVAL_ID,
        approved=approved,
    )

    with pytest.raises(
        IncidentContinuationClaimError
    ):
        continuation.recover_claimed_before_approval(
            approval_id=APPROVAL_ID,
            worker_id="worker-old",
            approval_store=approval,
        )

    still_claimed = continuation.get(
        APPROVAL_ID
    )

    assert (
        still_claimed.status
        == IncidentContinuationStatus.CLAIMED
    )


@pytest.mark.parametrize(
    "approved",
    [
        True,
        False,
    ],
)
def test_completed_approval_blocks_recovery(
    tmp_path,
    approved,
):
    continuation, approval = (
        _stores(
            tmp_path
        )
    )

    claimed = continuation.claim_next(
        worker_id="worker-old"
    )

    assert claimed is not None

    approval.claim(
        approval_id=APPROVAL_ID,
        approved=approved,
    )

    approval.complete(
        APPROVAL_ID
    )

    with pytest.raises(
        IncidentContinuationClaimError
    ):
        continuation.recover_claimed_before_approval(
            approval_id=APPROVAL_ID,
            worker_id="worker-old",
            approval_store=approval,
        )


def test_wrong_worker_blocks_recovery(
    tmp_path,
):
    continuation, approval = (
        _stores(
            tmp_path
        )
    )

    claimed = continuation.claim_next(
        worker_id="worker-old"
    )

    assert claimed is not None

    with pytest.raises(
        IncidentContinuationClaimError
    ):
        continuation.recover_claimed_before_approval(
            approval_id=APPROVAL_ID,
            worker_id="worker-other",
            approval_store=approval,
        )

    assert (
        continuation.get(
            APPROVAL_ID
        ).status
        == IncidentContinuationStatus.CLAIMED
    )


def test_pending_job_cannot_be_recovered_as_claimed(
    tmp_path,
):
    continuation, approval = (
        _stores(
            tmp_path
        )
    )

    with pytest.raises(
        IncidentContinuationClaimError
    ):
        continuation.recover_claimed_before_approval(
            approval_id=APPROVAL_ID,
            worker_id="worker-old",
            approval_store=approval,
        )


def test_recovery_survives_restart(
    tmp_path,
):
    continuation_db = (
        tmp_path
        / "continuation.db"
    )

    approval_db = (
        tmp_path
        / "approval.db"
    )

    first_continuation = (
        SqliteIncidentContinuationStore(
            continuation_db
        )
    )

    approval = (
        SqlitePendingApprovalStore(
            approval_db
        )
    )

    approval.register(
        PendingApprovalCorrelation(
            approval_id=APPROVAL_ID,
            workflow_id=WORKFLOW_ID,
            request_id=REQUEST_ID,
            checkpoint_id=CHECKPOINT_ID,
        )
    )

    first_continuation.enqueue(
        _invocation()
    )

    first_continuation.claim_next(
        worker_id="worker-old"
    )

    restarted_continuation = (
        SqliteIncidentContinuationStore(
            continuation_db
        )
    )

    restarted_approval = (
        SqlitePendingApprovalStore(
            approval_db
        )
    )

    recovered = (
        restarted_continuation
        .recover_claimed_before_approval(
            approval_id=APPROVAL_ID,
            worker_id="worker-old",
            approval_store=restarted_approval,
        )
    )

    assert (
        recovered.status
        == IncidentContinuationStatus.PENDING
    )


def test_recovery_does_not_change_authorized_payload(
    tmp_path,
):
    continuation, approval = (
        _stores(
            tmp_path
        )
    )

    before = continuation.get(
        APPROVAL_ID
    ).invocation

    continuation.claim_next(
        worker_id="worker-old"
    )

    recovered = (
        continuation
        .recover_claimed_before_approval(
            approval_id=APPROVAL_ID,
            worker_id="worker-old",
            approval_store=approval,
        )
    )

    assert recovered.invocation == before