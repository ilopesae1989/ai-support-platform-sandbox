import pytest

from pydantic import (
    ValidationError,
)

from src.runtime.procedure.approval_correlation import (
    ApprovalCorrelationNotFoundError,
    ApprovalCorrelationRegistry,
    DuplicateApprovalCorrelationError,
    PendingApprovalCorrelation,
    build_pending_approval_correlation,
)

from src.runtime.procedure.workflow import (
    ProcedureApprovalExecutor,
)

from tests.runtime.procedure.test_approval_request_integrity import (
    APPROVAL_ID,
    WORKFLOW_ID,
    create_pending_state,
)


REQUEST_ID = (
    "req-agent-framework-001"
)

CHECKPOINT_ID = (
    "checkpoint-hitl-001"
)


def create_approval_request():
    executor = (
        ProcedureApprovalExecutor()
    )

    state = (
        create_pending_state()
    )

    return (
        executor._build_approval_request(
            state
        )
    )


def create_correlation(
    *,
    request_id: str = REQUEST_ID,
):
    return (
        build_pending_approval_correlation(
            request=(
                create_approval_request()
            ),

            request_id=(
                request_id
            ),

            checkpoint_id=(
                CHECKPOINT_ID
            ),
        )
    )


def test_correlation_uses_identity_from_original_approval_request():
    correlation = (
        create_correlation()
    )

    assert (
        correlation.approval_id
        == APPROVAL_ID
    )

    assert (
        correlation.workflow_id
        == WORKFLOW_ID
    )

    assert (
        correlation.request_id
        == REQUEST_ID
    )

    assert (
        correlation.checkpoint_id
        == CHECKPOINT_ID
    )


def test_correlation_contains_no_operational_authority():
    correlation = (
        create_correlation()
    )

    assert (
        correlation.model_dump()
        == {
            "approval_id": (
                APPROVAL_ID
            ),

            "workflow_id": (
                WORKFLOW_ID
            ),

            "request_id": (
                REQUEST_ID
            ),

            "checkpoint_id": (
                CHECKPOINT_ID
            ),
        }
    )

    assert not hasattr(
        correlation,
        "procedure_id",
    )

    assert not hasattr(
        correlation,
        "capability_id",
    )

    assert not hasattr(
        correlation,
        "operation_action",
    )

    assert not hasattr(
        correlation,
        "target_resource",
    )

    assert not hasattr(
        correlation,
        "resolved_parameters",
    )


@pytest.mark.parametrize(
    (
        "field_name",
        "field_value",
    ),
    [
        (
            "approval_id",
            "",
        ),
        (
            "workflow_id",
            "",
        ),
        (
            "request_id",
            "",
        ),
        (
            "checkpoint_id",
            "",
        ),
        (
            "request_id",
            " req-001",
        ),
        (
            "checkpoint_id",
            "checkpoint-001 ",
        ),
    ],
)
def test_invalid_correlation_identity_is_rejected(
    field_name,
    field_value,
):
    payload = {
        "approval_id": (
            APPROVAL_ID
        ),

        "workflow_id": (
            WORKFLOW_ID
        ),

        "request_id": (
            REQUEST_ID
        ),

        "checkpoint_id": (
            CHECKPOINT_ID
        ),
    }

    payload[
        field_name
    ] = field_value

    with pytest.raises(
        ValidationError,
    ):
        PendingApprovalCorrelation(
            **payload
        )


def test_correlation_is_immutable():
    correlation = (
        create_correlation()
    )

    with pytest.raises(
        ValidationError,
    ):
        correlation.request_id = (
            "req-attacker"
        )


def test_registry_resolves_exact_approval_id():
    registry = (
        ApprovalCorrelationRegistry()
    )

    correlation = (
        create_correlation()
    )

    registry.register(
        correlation
    )

    assert (
        registry.get_by_approval_id(
            APPROVAL_ID
        )
        is correlation
    )


def test_registry_resolves_exact_request_id():
    registry = (
        ApprovalCorrelationRegistry()
    )

    correlation = (
        create_correlation()
    )

    registry.register(
        correlation
    )

    assert (
        registry.get_by_request_id(
            REQUEST_ID
        )
        is correlation
    )


def test_unknown_approval_id_fails_closed():
    registry = (
        ApprovalCorrelationRegistry()
    )

    registry.register(
        create_correlation()
    )

    with pytest.raises(
        ApprovalCorrelationNotFoundError,
    ):
        registry.get_by_approval_id(
            "apr-attacker"
        )


def test_duplicate_approval_id_is_rejected():
    registry = (
        ApprovalCorrelationRegistry()
    )

    registry.register(
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
        match="approval_id",
    ):
        registry.register(
            duplicate
        )


def test_duplicate_request_id_is_rejected():
    registry = (
        ApprovalCorrelationRegistry()
    )

    first = (
        create_correlation()
    )

    registry.register(
        first
    )

    second = (
        PendingApprovalCorrelation(
            approval_id=(
                "apr-22222222-2222-4222-"
                "8222-222222222222"
            ),

            workflow_id=(
                "wf-22222222-2222-4222-"
                "8222-222222222222"
            ),

            request_id=(
                REQUEST_ID
            ),

            checkpoint_id=(
                "checkpoint-hitl-002"
            ),
        )
    )

    with pytest.raises(
        DuplicateApprovalCorrelationError,
        match="request_id",
    ):
        registry.register(
            second
        )