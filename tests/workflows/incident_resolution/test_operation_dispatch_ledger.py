import pytest

from src.workflows.incident_resolution.operation_dispatch_ledger import (
    InMemoryOperationDispatchLedger,
    OperationAlreadyDispatchedError,
)


OPERATION_ID = (
    "op-11111111-1111-4111-"
    "8111-111111111111"
)


def test_first_claim_succeeds():
    ledger = (
        InMemoryOperationDispatchLedger()
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

    assert (
        ledger.count()
        == 1
    )


def test_second_claim_of_same_operation_is_rejected():
    ledger = (
        InMemoryOperationDispatchLedger()
    )

    ledger.claim(
        OPERATION_ID
    )

    with pytest.raises(
        OperationAlreadyDispatchedError,
        match=(
            "ya fue despachada"
        ),
    ):
        ledger.claim(
            OPERATION_ID
        )

    assert (
        ledger.count()
        == 1
    )


def test_different_operations_can_be_claimed():
    ledger = (
        InMemoryOperationDispatchLedger()
    )

    ledger.claim(
        OPERATION_ID
    )

    ledger.claim(
        (
            "op-22222222-2222-4222-"
            "8222-222222222222"
        )
    )

    assert (
        ledger.count()
        == 2
    )


@pytest.mark.parametrize(
    "invalid_operation_id",
    [
        "",
        "   ",
        None,
    ],
)
def test_invalid_operation_id_is_rejected(
    invalid_operation_id,
):
    ledger = (
        InMemoryOperationDispatchLedger()
    )

    with pytest.raises(
        ValueError,
        match=(
            "operation_id"
        ),
    ):
        ledger.claim(
            invalid_operation_id
        )

    assert (
        ledger.count()
        == 0
    )