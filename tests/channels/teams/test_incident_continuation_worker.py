from __future__ import annotations

from types import (
    SimpleNamespace,
)

import pytest

from src.channels.teams.approval_authorization import (
    AuthorizedTeamsApprovalInvocation,
)

from src.channels.teams.incident_continuation_store import (
    IncidentContinuationStatus,
    SqliteIncidentContinuationStore,
)

from src.channels.teams.incident_continuation_worker import (
    IncidentContinuationWorker,
    IncidentContinuationWorkerDependencies,
    IncidentContinuationWorkerOutcome,
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


APPROVAL_ID = "apr-worker-test"

WORKFLOW_ID = "wf-worker-test"

REQUEST_ID = "req-worker-test"

CHECKPOINT_ID = "cp-worker-test"


def _invocation():
    return AuthorizedTeamsApprovalInvocation(
        policy_id="teams-hitl-sandbox-v1",

        operator=TeamsOperatorIdentity(
            tenant_id="tenant-worker-test",
            aad_object_id="aad-worker-test",
            teams_user_id="teams-worker-test",
            conversation_id=(
                "conversation-worker-test"
            ),
            display_name="Worker Tester",
        ),

        action=ApprovalChannelAction(
            approval_id=APPROVAL_ID,
            decision=ApprovalDecision.APPROVE,
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


@pytest.mark.asyncio
async def test_successful_job_completes_after_notifier(
    tmp_path,
):
    continuation, approval = (
        _stores(
            tmp_path
        )
    )

    events = []

    async def processor(
        *,
        invocation,
        store,
        workflow,
    ):
        events.append(
            "processor"
        )

        store.claim(
            approval_id=APPROVAL_ID,
            approved=True,
        )

        store.complete(
            APPROVAL_ID
        )

        return SimpleNamespace(
            workflow_result="terminal-local"
        )

    async def notifier(
        *,
        invocation,
        processed,
    ):
        events.append(
            "notifier"
        )

    worker = IncidentContinuationWorker(
        IncidentContinuationWorkerDependencies(
            continuation_store=continuation,
            approval_store=approval,
            workflow_factory=(
                lambda: "workflow-local"
            ),
            processor=processor,
            terminal_notifier=notifier,
            worker_id="worker-local-1",
        )
    )

    outcome = await (
        worker.process_next_once()
    )

    assert (
        outcome
        == IncidentContinuationWorkerOutcome
        .COMPLETED
    )

    assert events == [
        "processor",
        "notifier",
    ]

    final = continuation.get(
        APPROVAL_ID
    )

    assert (
        final.status
        == IncidentContinuationStatus.COMPLETED
    )


@pytest.mark.asyncio
async def test_preapproval_failure_is_safely_requeued(
    tmp_path,
):
    continuation, approval = (
        _stores(
            tmp_path
        )
    )

    async def processor(**kwargs):
        raise RuntimeError(
            "synthetic preapproval failure"
        )

    async def notifier(**kwargs):
        raise AssertionError(
            "notifier no debe ejecutarse"
        )

    worker = IncidentContinuationWorker(
        IncidentContinuationWorkerDependencies(
            continuation_store=continuation,
            approval_store=approval,
            workflow_factory=lambda: object(),
            processor=processor,
            terminal_notifier=notifier,
            worker_id="worker-local-1",
        )
    )

    outcome = await (
        worker.process_next_once()
    )

    assert (
        outcome
        == IncidentContinuationWorkerOutcome
        .REQUEUED_PREAPPROVAL
    )

    final = continuation.get(
        APPROVAL_ID
    )

    assert (
        final.status
        == IncidentContinuationStatus.PENDING
    )


@pytest.mark.asyncio
async def test_postapproval_failure_fails_closed(
    tmp_path,
):
    continuation, approval = (
        _stores(
            tmp_path
        )
    )

    async def processor(
        *,
        invocation,
        store,
        workflow,
    ):
        store.claim(
            approval_id=APPROVAL_ID,
            approved=True,
        )

        raise RuntimeError(
            "synthetic postapproval failure"
        )

    async def notifier(**kwargs):
        raise AssertionError(
            "notifier no debe ejecutarse"
        )

    worker = IncidentContinuationWorker(
        IncidentContinuationWorkerDependencies(
            continuation_store=continuation,
            approval_store=approval,
            workflow_factory=lambda: object(),
            processor=processor,
            terminal_notifier=notifier,
            worker_id="worker-local-1",
        )
    )

    outcome = await (
        worker.process_next_once()
    )

    assert (
        outcome
        == IncidentContinuationWorkerOutcome
        .FAILED_CLOSED
    )

    final = continuation.get(
        APPROVAL_ID
    )

    assert (
        final.status
        == IncidentContinuationStatus.FAILED
    )

    assert (
        final.last_error
        == "RuntimeError"
    )


@pytest.mark.asyncio
async def test_notifier_failure_after_approval_never_requeues(
    tmp_path,
):
    continuation, approval = (
        _stores(
            tmp_path
        )
    )

    async def processor(
        *,
        invocation,
        store,
        workflow,
    ):
        store.claim(
            approval_id=APPROVAL_ID,
            approved=True,
        )

        store.complete(
            APPROVAL_ID
        )

        return SimpleNamespace(
            workflow_result="terminal-local"
        )

    async def notifier(**kwargs):
        raise RuntimeError(
            "synthetic outbound failure"
        )

    worker = IncidentContinuationWorker(
        IncidentContinuationWorkerDependencies(
            continuation_store=continuation,
            approval_store=approval,
            workflow_factory=lambda: object(),
            processor=processor,
            terminal_notifier=notifier,
            worker_id="worker-local-1",
        )
    )

    outcome = await (
        worker.process_next_once()
    )

    assert (
        outcome
        == IncidentContinuationWorkerOutcome
        .FAILED_CLOSED
    )

    final = continuation.get(
        APPROVAL_ID
    )

    assert (
        final.status
        == IncidentContinuationStatus.FAILED
    )

    assert (
        final.last_error
        == "RuntimeError"
    )


@pytest.mark.asyncio
async def test_idle_worker_has_no_side_effect(
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

    async def should_not_run(**kwargs):
        raise AssertionError(
            "no debe ejecutarse"
        )

    worker = IncidentContinuationWorker(
        IncidentContinuationWorkerDependencies(
            continuation_store=continuation,
            approval_store=approval,
            workflow_factory=lambda: object(),
            processor=should_not_run,
            terminal_notifier=should_not_run,
            worker_id="worker-local-1",
        )
    )

    outcome = await (
        worker.process_next_once()
    )

    assert (
        outcome
        == IncidentContinuationWorkerOutcome
        .IDLE
    )