from __future__ import annotations

import ast

from pathlib import Path

import pytest

from src.channels.teams.approval_authorization import (
    AuthorizedTeamsApprovalInvocation,
)

from src.channels.teams.incident_approval_handoff_handler import (
    enqueue_authorized_teams_incident_approval,
)

from src.channels.teams.incident_continuation_store import (
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

from src.runtime.procedure.approval_correlation import (
    ApprovalCorrelationNotFoundError,
    PendingApprovalCorrelation,
)

from src.runtime.procedure.approval_store import (
    SqlitePendingApprovalStore,
)


APPROVAL_ID = "apr-handoff-4341a"


def _invocation(
    decision=ApprovalDecision.APPROVE,
):
    return AuthorizedTeamsApprovalInvocation(
        policy_id="teams-hitl-sandbox-v1",
        operator=TeamsOperatorIdentity(
            tenant_id="tenant-handoff",
            aad_object_id="aad-handoff",
            teams_user_id="teams-handoff",
            conversation_id="conversation-handoff",
        ),
        action=ApprovalChannelAction(
            approval_id=APPROVAL_ID,
            decision=decision,
        ),
    )


def _stores(tmp_path):
    approval = SqlitePendingApprovalStore(
        tmp_path / "approval.db"
    )

    continuation = SqliteIncidentContinuationStore(
        tmp_path / "continuation.db"
    )

    approval.register(
        PendingApprovalCorrelation(
            approval_id=APPROVAL_ID,
            workflow_id="wf-handoff",
            request_id="req-handoff",
            checkpoint_id="cp-handoff",
        )
    )

    return approval, continuation


def test_approve_is_enqueued_without_consuming_approval(
    tmp_path,
):
    approval, continuation = _stores(
        tmp_path
    )

    approved = (
        enqueue_authorized_teams_incident_approval(
            invocation=_invocation(),
            store=approval,
            continuation_store=continuation,
        )
    )

    assert approved is True

    assert (
        continuation.get(
            APPROVAL_ID
        ).status
        == IncidentContinuationStatus.PENDING
    )

    assert (
        approval.get_consumption_record(
            APPROVAL_ID
        )
        == (
            "pending",
            None,
        )
    )


def test_exact_retry_is_idempotent(
    tmp_path,
):
    approval, continuation = _stores(
        tmp_path
    )

    invocation = _invocation()

    enqueue_authorized_teams_incident_approval(
        invocation=invocation,
        store=approval,
        continuation_store=continuation,
    )

    enqueue_authorized_teams_incident_approval(
        invocation=invocation,
        store=approval,
        continuation_store=continuation,
    )

    assert (
        continuation.get(
            APPROVAL_ID
        ).attempt_count
        == 0
    )


def test_decision_substitution_fails_closed(
    tmp_path,
):
    approval, continuation = _stores(
        tmp_path
    )

    enqueue_authorized_teams_incident_approval(
        invocation=_invocation(
            ApprovalDecision.APPROVE
        ),
        store=approval,
        continuation_store=continuation,
    )

    with pytest.raises(
        IncidentContinuationConflictError
    ):
        enqueue_authorized_teams_incident_approval(
            invocation=_invocation(
                ApprovalDecision.REJECT
            ),
            store=approval,
            continuation_store=continuation,
        )


def test_fast_handler_contains_no_operational_await():
    path = Path(
        "src/channels/teams/"
        "incident_approval_handoff_handler.py"
    )

    tree = ast.parse(
        path.read_text(
            encoding="utf-8"
        )
    )

    target = None

    for node in tree.body:
        if (
            isinstance(
                node,
                ast.AsyncFunctionDef,
            )
            and node.name
            == "handle_teams_approval_action"
        ):
            target = node
            break

    assert target is not None

    awaits = [
        node
        for node in ast.walk(target)
        if isinstance(node, ast.Await)
    ]

    assert len(awaits) == 1

    awaited_value = awaits[0].value

    assert isinstance(
        awaited_value,
        ast.Call,
    )

    assert isinstance(
        awaited_value.func,
        ast.Name,
    )

    assert (
        awaited_value.func.id
        == "authorize_teams_approval_invocation"
    )

    source = ast.unparse(target)

    assert "workflow.run" not in source
    assert "workflow_factory" not in source
    assert ".processor" not in source

# TDD_PHASE23_FAILED_CONTINUATION_REPLAY_RED
def test_phase23_failed_continuation_rejects_exact_replay(
    tmp_path,
):
    """
    Un continuation job terminal FAILED no puede
    aceptar de nuevo el mismo Action.Execute como
    si existiera trabajo pendiente.

    La aprobación puede seguir pending/NULL porque
    el fallo ocurrió antes de store.claim(), pero
    el handoff FAILED es terminal y no será
    reclamado por ningún worker.
    """

    approval, continuation = _stores(
        tmp_path
    )

    invocation = _invocation(
        ApprovalDecision.REJECT
    )

    enqueue_authorized_teams_incident_approval(
        invocation=invocation,
        store=approval,
        continuation_store=continuation,
    )

    claimed = continuation.claim_next(
        worker_id="worker-phase23-terminal"
    )

    assert claimed is not None

    failed = continuation.fail(
        approval_id=APPROVAL_ID,
        worker_id="worker-phase23-terminal",
        error="SyntheticPreApprovalFailure",
    )

    assert (
        failed.status
        == IncidentContinuationStatus.FAILED
    )

    assert (
        approval.get_consumption_record(
            APPROVAL_ID
        )
        == (
            "pending",
            None,
        )
    )

    with pytest.raises(
        IncidentContinuationConflictError,
    ):
        enqueue_authorized_teams_incident_approval(
            invocation=invocation,
            store=approval,
            continuation_store=continuation,
        )

    final = continuation.get(
        APPROVAL_ID
    )

    assert (
        final.status
        == IncidentContinuationStatus.FAILED
    )

    assert final.attempt_count == 1