from __future__ import annotations

from concurrent.futures import (
    ThreadPoolExecutor,
)

import pytest

from src.channels.teams.approval_authorization import (
    AuthorizedTeamsApprovalInvocation,
)

from src.channels.teams.incident_continuation_store import (
    IncidentContinuationClaimError,
    IncidentContinuationConflictError,
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


def _invocation(
    *,
    approval_id: str = "apr-local-handoff-001",
    decision: ApprovalDecision = (
        ApprovalDecision.APPROVE
    ),
    aad_object_id: str = "aad-local-approver-001",
) -> AuthorizedTeamsApprovalInvocation:
    return AuthorizedTeamsApprovalInvocation(
        policy_id=(
            "teams-hitl-sandbox-v1"
        ),

        operator=TeamsOperatorIdentity(
            tenant_id=(
                "tenant-local-001"
            ),

            aad_object_id=(
                aad_object_id
            ),

            teams_user_id=(
                "teams-user-local-001"
            ),

            conversation_id=(
                "conversation-local-001"
            ),

            display_name=(
                "Local Approver"
            ),
        ),

        action=ApprovalChannelAction(
            approval_id=approval_id,
            decision=decision,
        ),
    )


def test_enqueue_survives_store_restart(
    tmp_path,
):
    database = (
        tmp_path
        / "continuations.db"
    )

    first = (
        SqliteIncidentContinuationStore(
            database
        )
    )

    invocation = (
        _invocation()
    )

    queued = first.enqueue(
        invocation
    )

    assert (
        queued.status
        == IncidentContinuationStatus.PENDING
    )

    second = (
        SqliteIncidentContinuationStore(
            database
        )
    )

    restored = second.get(
        invocation.action.approval_id
    )

    assert (
        restored.invocation
        == invocation
    )

    assert (
        restored.status
        == IncidentContinuationStatus.PENDING
    )


def test_exact_duplicate_enqueue_is_idempotent(
    tmp_path,
):
    store = (
        SqliteIncidentContinuationStore(
            tmp_path
            / "continuations.db"
        )
    )

    invocation = (
        _invocation()
    )

    first = store.enqueue(
        invocation
    )

    second = store.enqueue(
        invocation
    )

    assert (
        second.approval_id
        == first.approval_id
    )

    assert (
        second.invocation
        == first.invocation
    )

    assert (
        second.status
        == first.status
    )

    assert second.attempt_count == 0


def test_same_approval_id_with_different_decision_fails_closed(
    tmp_path,
):
    store = (
        SqliteIncidentContinuationStore(
            tmp_path
            / "continuations.db"
        )
    )

    store.enqueue(
        _invocation(
            decision=(
                ApprovalDecision.APPROVE
            )
        )
    )

    with pytest.raises(
        IncidentContinuationConflictError
    ):
        store.enqueue(
            _invocation(
                decision=(
                    ApprovalDecision.REJECT
                )
            )
        )


def test_same_approval_id_with_different_operator_fails_closed(
    tmp_path,
):
    store = (
        SqliteIncidentContinuationStore(
            tmp_path
            / "continuations.db"
        )
    )

    store.enqueue(
        _invocation()
    )

    with pytest.raises(
        IncidentContinuationConflictError
    ):
        store.enqueue(
            _invocation(
                aad_object_id=(
                    "aad-other-approver"
                )
            )
        )


def test_claim_is_atomic_across_store_instances(
    tmp_path,
):
    database = (
        tmp_path
        / "continuations.db"
    )

    SqliteIncidentContinuationStore(
        database
    ).enqueue(
        _invocation()
    )

    def claim(
        worker_number: int,
    ):
        local_store = (
            SqliteIncidentContinuationStore(
                database
            )
        )

        return local_store.claim_next(
            worker_id=(
                f"worker-{worker_number}"
            )
        )

    with ThreadPoolExecutor(
        max_workers=8
    ) as executor:
        results = list(
            executor.map(
                claim,
                range(8),
            )
        )

    claimed = [
        result
        for result
        in results
        if result is not None
    ]

    assert len(claimed) == 1

    assert (
        claimed[0].status
        == IncidentContinuationStatus.CLAIMED
    )

    assert claimed[0].attempt_count == 1


def test_claimed_job_survives_restart_and_is_not_reclaimed(
    tmp_path,
):
    database = (
        tmp_path
        / "continuations.db"
    )

    first = (
        SqliteIncidentContinuationStore(
            database
        )
    )

    first.enqueue(
        _invocation()
    )

    claimed = first.claim_next(
        worker_id="worker-1"
    )

    assert claimed is not None

    second = (
        SqliteIncidentContinuationStore(
            database
        )
    )

    restored = second.get(
        claimed.approval_id
    )

    assert (
        restored.status
        == IncidentContinuationStatus.CLAIMED
    )

    assert (
        restored.claimed_by
        == "worker-1"
    )

    assert (
        second.claim_next(
            worker_id="worker-2"
        )
        is None
    )


def test_complete_requires_claim_owner(
    tmp_path,
):
    store = (
        SqliteIncidentContinuationStore(
            tmp_path
            / "continuations.db"
        )
    )

    store.enqueue(
        _invocation()
    )

    claimed = store.claim_next(
        worker_id="worker-1"
    )

    assert claimed is not None

    with pytest.raises(
        IncidentContinuationClaimError
    ):
        store.complete(
            approval_id=(
                claimed.approval_id
            ),
            worker_id="worker-2",
        )

    completed = store.complete(
        approval_id=(
            claimed.approval_id
        ),
        worker_id="worker-1",
    )

    assert (
        completed.status
        == IncidentContinuationStatus.COMPLETED
    )

    assert completed.claimed_by is None

    assert (
        store.claim_next(
            worker_id="worker-3"
        )
        is None
    )


def test_failed_job_is_terminal_and_not_reclaimed(
    tmp_path,
):
    store = (
        SqliteIncidentContinuationStore(
            tmp_path
            / "continuations.db"
        )
    )

    store.enqueue(
        _invocation()
    )

    claimed = store.claim_next(
        worker_id="worker-1"
    )

    assert claimed is not None

    failed = store.fail(
        approval_id=(
            claimed.approval_id
        ),
        worker_id="worker-1",
        error=(
            "LOCAL TEST FAILURE"
        ),
    )

    assert (
        failed.status
        == IncidentContinuationStatus.FAILED
    )

    assert (
        failed.last_error
        == "LOCAL TEST FAILURE"
    )

    assert failed.claimed_by is None

    assert (
        store.claim_next(
            worker_id="worker-2"
        )
        is None
    )


def test_channel_payload_contains_no_operational_authority(
    tmp_path,
):
    store = (
        SqliteIncidentContinuationStore(
            tmp_path
            / "continuations.db"
        )
    )

    job = store.enqueue(
        _invocation()
    )

    payload = (
        job.invocation.model_dump(
            mode="json"
        )
    )

    serialized = str(
        payload
    )

    forbidden = (
        "procedure_id",
        "capability_id",
        "operation_action",
        "target_resource",
        "required_parameters",
        "resolved_parameters",
        "subscription_id",
        "resource_group",
        "vm_name",
    )

    for token in forbidden:
        assert token not in serialized