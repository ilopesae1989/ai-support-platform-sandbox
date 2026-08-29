from __future__ import annotations

import pytest

from src.runtime.procedure.approval_correlation import (
    ApprovalCorrelationNotFoundError,
    PendingApprovalCorrelation,
)

from src.runtime.procedure.approval_store import (
    SqlitePendingApprovalStore,
)

from src.workflows.incident_resolution.operation_dispatch_ledger import (
    OperationAlreadyDispatchedError,
    SqliteOperationDispatchLedger,
)


APPROVAL_ID = "apr-recovery-observation-001"

WORKFLOW_ID = "wf-recovery-observation-001"

REQUEST_ID = "req-recovery-observation-001"

CHECKPOINT_ID = "cp-recovery-observation-001"

OPERATION_ID = "op-recovery-observation-001"


def _correlation():
    return PendingApprovalCorrelation(
        approval_id=APPROVAL_ID,
        workflow_id=WORKFLOW_ID,
        request_id=REQUEST_ID,
        checkpoint_id=CHECKPOINT_ID,
    )


def test_pending_approval_record_exposes_no_decision(
    tmp_path,
):
    store = SqlitePendingApprovalStore(
        tmp_path / "approvals.db"
    )

    store.register(
        _correlation()
    )

    status, approved = (
        store.get_consumption_record(
            APPROVAL_ID
        )
    )

    assert status == "pending"
    assert approved is None


@pytest.mark.parametrize(
    "approved",
    [
        True,
        False,
    ],
)
def test_claimed_approval_preserves_exact_decision(
    tmp_path,
    approved,
):
    store = SqlitePendingApprovalStore(
        tmp_path / "approvals.db"
    )

    store.register(
        _correlation()
    )

    store.claim(
        approval_id=APPROVAL_ID,
        approved=approved,
    )

    status, observed = (
        store.get_consumption_record(
            APPROVAL_ID
        )
    )

    assert status == "claimed"
    assert observed is approved

    restarted = SqlitePendingApprovalStore(
        tmp_path / "approvals.db"
    )

    status_after, observed_after = (
        restarted.get_consumption_record(
            APPROVAL_ID
        )
    )

    assert status_after == "claimed"
    assert observed_after is approved


@pytest.mark.parametrize(
    "approved",
    [
        True,
        False,
    ],
)
def test_completed_approval_preserves_exact_decision(
    tmp_path,
    approved,
):
    database = (
        tmp_path / "approvals.db"
    )

    store = SqlitePendingApprovalStore(
        database
    )

    store.register(
        _correlation()
    )

    store.claim(
        approval_id=APPROVAL_ID,
        approved=approved,
    )

    store.complete(
        APPROVAL_ID
    )

    restarted = SqlitePendingApprovalStore(
        database
    )

    status, observed = (
        restarted.get_consumption_record(
            APPROVAL_ID
        )
    )

    assert status == "completed"
    assert observed is approved


def test_consumption_record_unknown_approval_fails_closed(
    tmp_path,
):
    store = SqlitePendingApprovalStore(
        tmp_path / "approvals.db"
    )

    with pytest.raises(
        ApprovalCorrelationNotFoundError
    ):
        store.get_consumption_record(
            "apr-does-not-exist"
        )


def test_sqlite_dispatch_contains_is_false_before_claim(
    tmp_path,
):
    ledger = SqliteOperationDispatchLedger(
        tmp_path / "dispatch.db"
    )

    assert (
        ledger.contains(
            OPERATION_ID
        )
        is False
    )


def test_sqlite_dispatch_contains_survives_restart(
    tmp_path,
):
    database = (
        tmp_path / "dispatch.db"
    )

    first = SqliteOperationDispatchLedger(
        database
    )

    first.claim(
        OPERATION_ID
    )

    assert (
        first.contains(
            OPERATION_ID
        )
        is True
    )

    second = SqliteOperationDispatchLedger(
        database
    )

    assert (
        second.contains(
            OPERATION_ID
        )
        is True
    )


def test_sqlite_dispatch_observation_does_not_consume(
    tmp_path,
):
    ledger = SqliteOperationDispatchLedger(
        tmp_path / "dispatch.db"
    )

    assert (
        ledger.contains(
            OPERATION_ID
        )
        is False
    )

    ledger.claim(
        OPERATION_ID
    )

    assert (
        ledger.contains(
            OPERATION_ID
        )
        is True
    )

    with pytest.raises(
        OperationAlreadyDispatchedError
    ):
        ledger.claim(
            OPERATION_ID
        )


def test_sqlite_dispatch_contains_rejects_invalid_id(
    tmp_path,
):
    ledger = SqliteOperationDispatchLedger(
        tmp_path / "dispatch.db"
    )

    with pytest.raises(
        ValueError
    ):
        ledger.contains(
            "   "
        )