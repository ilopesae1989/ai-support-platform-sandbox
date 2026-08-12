import pytest

from pydantic import (
    ValidationError,
)

from src.runtime.procedure.approval_channel import (
    ApprovalChannelAction,
    ApprovalDecision,
)


APPROVAL_ID = (
    "apr-11111111-1111-4111-"
    "8111-111111111111"
)


def test_approve_action_contains_only_minimal_decision():
    action = (
        ApprovalChannelAction.model_validate(
            {
                "approval_id": (
                    APPROVAL_ID
                ),

                "decision": (
                    "approve"
                ),
            }
        )
    )

    assert (
        action.approval_id
        == APPROVAL_ID
    )

    assert (
        action.decision
        == ApprovalDecision.APPROVE
    )

    assert (
        action.model_dump(
            mode="json"
        )
        == {
            "approval_id": (
                APPROVAL_ID
            ),

            "decision": (
                "approve"
            ),
        }
    )


def test_reject_action_is_supported():
    action = (
        ApprovalChannelAction.model_validate(
            {
                "approval_id": (
                    APPROVAL_ID
                ),

                "decision": (
                    "reject"
                ),
            }
        )
    )

    assert (
        action.decision
        == ApprovalDecision.REJECT
    )


def test_unknown_decision_is_rejected():
    with pytest.raises(
        ValidationError,
    ):
        ApprovalChannelAction.model_validate(
            {
                "approval_id": (
                    APPROVAL_ID
                ),

                "decision": (
                    "execute"
                ),
            }
        )


@pytest.mark.parametrize(
    "approval_id",
    [
        "",
        " ",
        "  apr-test",
        "apr-test  ",
    ],
)
def test_invalid_approval_id_is_rejected(
    approval_id,
):
    with pytest.raises(
        ValidationError,
    ):
        ApprovalChannelAction.model_validate(
            {
                "approval_id": (
                    approval_id
                ),

                "decision": (
                    "approve"
                ),
            }
        )


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "workflow_id",
        "alert_id",
        "correlation_id",
        "conversation_id",
        "procedure_id",
        "procedure_version",
        "current_step",
        "step_id",
        "description",
        "operation_domain",
        "operation_kind",
        "operation_action",
        "capability_id",
        "hitl_required",
        "next_action",
        "target_resource",
        "required_parameters",
        "resolved_parameters",
        "subscription_id",
        "resource_group",
        "vm_name",
        "tenant_id",
        "operator_id",
    ],
)
def test_channel_cannot_supply_operational_authority(
    forbidden_field,
):
    payload = {
        "approval_id": (
            APPROVAL_ID
        ),

        "decision": (
            "approve"
        ),

        forbidden_field: (
            "attacker-controlled-value"
        ),
    }

    with pytest.raises(
        ValidationError,
    ):
        ApprovalChannelAction.model_validate(
            payload
        )


def test_channel_action_is_immutable():
    action = (
        ApprovalChannelAction(
            approval_id=(
                APPROVAL_ID
            ),

            decision=(
                ApprovalDecision.APPROVE
            ),
        )
    )

    with pytest.raises(
        ValidationError,
    ):
        action.decision = (
            ApprovalDecision.REJECT
        )