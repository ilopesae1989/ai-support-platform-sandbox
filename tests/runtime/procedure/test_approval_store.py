import pytest

from src.runtime.procedure.approval_correlation import (
    ApprovalCorrelationNotFoundError,
    DuplicateApprovalCorrelationError,
    PendingApprovalCorrelation,
)

from src.runtime.procedure.approval_store import (
    ApprovalAlreadyConsumedError,
    SqlitePendingApprovalStore,
)


APPROVAL_ID = (
    "apr-11111111-1111-4111-"
    "8111-111111111111"
)

WORKFLOW_ID = (
    "wf-11111111-1111-4111-"
    "8111-111111111111"
)

REQUEST_ID = (
    "req-agent-framework-001"
)

CHECKPOINT_ID = (
    "checkpoint-hitl-001"
)


def create_correlation(
    *,
    approval_id: str = APPROVAL_ID,
    workflow_id: str = WORKFLOW_ID,
    request_id: str = REQUEST_ID,
    checkpoint_id: str = CHECKPOINT_ID,
) -> PendingApprovalCorrelation:
    return PendingApprovalCorrelation(
        approval_id=(
            approval_id
        ),

        workflow_id=(
            workflow_id
        ),

        request_id=(
            request_id
        ),

        checkpoint_id=(
            checkpoint_id
        ),
    )


def test_store_persists_correlation_between_instances(
    tmp_path,
):
    database = (
        tmp_path
        / "pending-approvals.db"
    )

    store_a = (
        SqlitePendingApprovalStore(
            database
        )
    )

    correlation = (
        create_correlation()
    )

    store_a.register(
        correlation
    )

    # Nueva instancia:
    # simula otro proceso/worker.
    store_b = (
        SqlitePendingApprovalStore(
            database
        )
    )

    restored = (
        store_b.get_by_approval_id(
            APPROVAL_ID
        )
    )

    assert (
        restored
        == correlation
    )


def test_store_resolves_exact_request_id(
    tmp_path,
):
    database = (
        tmp_path
        / "pending-approvals.db"
    )

    store = (
        SqlitePendingApprovalStore(
            database
        )
    )

    correlation = (
        create_correlation()
    )

    store.register(
        correlation
    )

    assert (
        store.get_by_request_id(
            REQUEST_ID
        )
        == correlation
    )


def test_unknown_approval_id_fails_closed(
    tmp_path,
):
    store = (
        SqlitePendingApprovalStore(
            tmp_path
            / "pending-approvals.db"
        )
    )

    with pytest.raises(
        ApprovalCorrelationNotFoundError,
    ):
        store.get_by_approval_id(
            "apr-attacker"
        )


def test_lookup_is_exact(
    tmp_path,
):
    store = (
        SqlitePendingApprovalStore(
            tmp_path
            / "pending-approvals.db"
        )
    )

    store.register(
        create_correlation()
    )

    with pytest.raises(
        ApprovalCorrelationNotFoundError,
    ):
        store.get_by_approval_id(
            APPROVAL_ID.upper()
        )


def test_duplicate_approval_id_is_rejected(
    tmp_path,
):
    store = (
        SqlitePendingApprovalStore(
            tmp_path
            / "pending-approvals.db"
        )
    )

    store.register(
        create_correlation()
    )

    duplicate = (
        create_correlation(
            request_id=(
                "req-agent-framework-002"
            )
        )
    )

    with pytest.raises(
        DuplicateApprovalCorrelationError,
    ):
        store.register(
            duplicate
        )


def test_duplicate_request_id_is_rejected(
    tmp_path,
):
    store = (
        SqlitePendingApprovalStore(
            tmp_path
            / "pending-approvals.db"
        )
    )

    store.register(
        create_correlation()
    )

    duplicate = (
        create_correlation(
            approval_id=(
                "apr-22222222-2222-4222-"
                "8222-222222222222"
            ),

            workflow_id=(
                "wf-22222222-2222-4222-"
                "8222-222222222222"
            ),
        )
    )

    with pytest.raises(
        DuplicateApprovalCorrelationError,
    ):
        store.register(
            duplicate
        )


@pytest.mark.parametrize(
    (
        "lookup_method",
        "value",
    ),
    [
        (
            "get_by_approval_id",
            "",
        ),
        (
            "get_by_approval_id",
            " ",
        ),
        (
            "get_by_approval_id",
            " apr-001",
        ),
        (
            "get_by_request_id",
            "",
        ),
        (
            "get_by_request_id",
            "req-001 ",
        ),
    ],
)
def test_invalid_lookup_identity_is_rejected(
    tmp_path,
    lookup_method,
    value,
):
    store = (
        SqlitePendingApprovalStore(
            tmp_path
            / "pending-approvals.db"
        )
    )

    method = getattr(
        store,
        lookup_method,
    )

    with pytest.raises(
        ValueError,
    ):
        method(
            value
        )


def test_store_contains_no_operational_authority(
    tmp_path,
):
    store = (
        SqlitePendingApprovalStore(
            tmp_path
            / "pending-approvals.db"
        )
    )

    store.register(
        create_correlation()
    )

    correlation = (
        store.get_by_approval_id(
            APPROVAL_ID
        )
    )

    payload = (
        correlation.model_dump()
    )

    assert set(
        payload
    ) == {
        "approval_id",
        "workflow_id",
        "request_id",
        "checkpoint_id",
    }


def test_pending_approval_can_be_claimed_once(
    tmp_path,
):
    database = (
        tmp_path
        / "pending-approvals.db"
    )

    store = (
        SqlitePendingApprovalStore(
            database
        )
    )

    correlation = (
        create_correlation()
    )

    store.register(
        correlation
    )

    claimed = (
        store.claim(
            approval_id=(
                APPROVAL_ID
            ),

            approved=True,
        )
    )

    assert (
        claimed
        == correlation
    )

    assert (
        store.get_consumption_status(
            APPROVAL_ID
        )
        == "claimed"
    )


def test_second_claim_is_rejected_as_replay(
    tmp_path,
):
    database = (
        tmp_path
        / "pending-approvals.db"
    )

    store_a = (
        SqlitePendingApprovalStore(
            database
        )
    )

    store_a.register(
        create_correlation()
    )

    store_a.claim(
        approval_id=(
            APPROVAL_ID
        ),

        approved=True,
    )

    # Nueva instancia:
    # simula otro worker o segundo click.
    store_b = (
        SqlitePendingApprovalStore(
            database
        )
    )

    with pytest.raises(
        ApprovalAlreadyConsumedError,
    ):
        store_b.claim(
            approval_id=(
                APPROVAL_ID
            ),

            approved=True,
        )


def test_second_claim_with_opposite_decision_is_also_rejected(
    tmp_path,
):
    database = (
        tmp_path
        / "pending-approvals.db"
    )

    store = (
        SqlitePendingApprovalStore(
            database
        )
    )

    store.register(
        create_correlation()
    )

    store.claim(
        approval_id=(
            APPROVAL_ID
        ),

        approved=True,
    )

    with pytest.raises(
        ApprovalAlreadyConsumedError,
    ):
        store.claim(
            approval_id=(
                APPROVAL_ID
            ),

            approved=False,
        )


def test_claim_can_be_completed_but_not_reopened(
    tmp_path,
):
    store = (
        SqlitePendingApprovalStore(
            tmp_path
            / "pending-approvals.db"
        )
    )

    store.register(
        create_correlation()
    )

    store.claim(
        approval_id=(
            APPROVAL_ID
        ),

        approved=False,
    )

    store.complete(
        APPROVAL_ID
    )

    assert (
        store.get_consumption_status(
            APPROVAL_ID
        )
        == "completed"
    )

    with pytest.raises(
        ApprovalAlreadyConsumedError,
    ):
        store.claim(
            approval_id=(
                APPROVAL_ID
            ),

            approved=True,
        )