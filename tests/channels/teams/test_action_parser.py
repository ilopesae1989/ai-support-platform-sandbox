import pytest

from pydantic import (
    ValidationError,
)

from microsoft_teams.api import (
    AdaptiveCardInvokeActivity,
)

from src.channels.teams.action_parser import (
    TeamsApprovalActionError,
    parse_teams_approval_action,
)

from src.runtime.procedure.approval_channel import (
    ApprovalChannelAction,
    ApprovalDecision,
)


APPROVAL_ID = (
    "apr-11111111-1111-4111-"
    "8111-111111111111"
)


def create_activity(
    *,
    action_type: str = "Action.Execute",
    action_name: str = "approval_decision",
    approval_id: str = APPROVAL_ID,
    decision: str = "approve",
    extra_data: dict | None = None,
    invoke_name: str = "adaptiveCard/action",
) -> AdaptiveCardInvokeActivity:
    data = {
        "action": (
            action_name
        ),

        "approval_id": (
            approval_id
        ),

        "decision": (
            decision
        ),
    }

    if extra_data:
        data.update(
            extra_data
        )

    return (
        AdaptiveCardInvokeActivity
        .model_validate(
            {
                "channelId": (
                    "msteams"
                ),

                "from": {
                    "id": (
                        "29:teams-user-001"
                    ),

                    "aadObjectId": (
                        "11111111-1111-4111-"
                        "8111-111111111111"
                    ),

                    "type": (
                        "person"
                    ),
                },

                "conversation": {
                    "id": (
                        "19:conversation-001"
                        "@thread.v2"
                    ),
                },

                "channelData": {
                    "tenant": {
                        "id": (
                            "0cb40b2b-6cfc-4c63-"
                            "bf7b-da710ea390cb"
                        ),
                    },
                },

                "id": (
                    "activity-001"
                ),

                "recipient": {
                    "id": (
                        "bot-ai-support"
                    ),

                    "type": (
                        "bot"
                    ),
                },

                "name": (
                    invoke_name
                ),

                "value": {
                    "action": {
                        "type": (
                            action_type
                        ),

                        "data": (
                            data
                        ),
                    },
                },
            }
        )
    )


def test_approve_execute_action_parses_to_channel_contract():
    activity = (
        create_activity()
    )

    action = (
        parse_teams_approval_action(
            activity
        )
    )

    assert (
        action
        == ApprovalChannelAction(
            approval_id=(
                APPROVAL_ID
            ),

            decision=(
                ApprovalDecision.APPROVE
            ),
        )
    )


def test_reject_execute_action_is_supported():
    action = (
        parse_teams_approval_action(
            create_activity(
                decision="reject"
            )
        )
    )

    assert (
        action.decision
        == ApprovalDecision.REJECT
    )


def test_unknown_routing_action_is_rejected():
    with pytest.raises(
        TeamsApprovalActionError,
    ):
        parse_teams_approval_action(
            create_activity(
                action_name=(
                    "delete_virtual_machine"
                )
            )
        )


def test_action_submit_is_rejected():
    with pytest.raises(
        TeamsApprovalActionError,
        match="Action.Execute",
    ):
        parse_teams_approval_action(
            create_activity(
                action_type=(
                    "Action.Submit"
                )
            )
        )


def test_sdk_rejects_wrong_invoke_name_before_parser():
    """
    AdaptiveCardInvokeActivity representa
    específicamente adaptiveCard/action.

    Una actividad con otro invoke name debe ser
    rechazada por el propio contrato tipado del
    Teams SDK antes de alcanzar nuestro parser.
    """

    with pytest.raises(
        ValidationError,
    ):
        create_activity(
            invoke_name=(
                "composeExtension/query"
            )
        )


def test_unknown_decision_is_rejected():
    with pytest.raises(
        TeamsApprovalActionError,
    ):
        parse_teams_approval_action(
            create_activity(
                decision=(
                    "execute"
                )
            )
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
        "aad_object_id",
        "teams_user_id",
        "operator_id",
        "display_name",
        "request_id",
        "checkpoint_id",
    ],
)
def test_action_data_cannot_supply_extra_authority(
    forbidden_field,
):
    with pytest.raises(
        TeamsApprovalActionError,
    ):
        parse_teams_approval_action(
            create_activity(
                extra_data={
                    forbidden_field:
                        "attacker-controlled"
                }
            )
        )


@pytest.mark.parametrize(
    "approval_id",
    [
        "",
        " ",
        " apr-test",
        "apr-test ",
    ],
)
def test_invalid_approval_id_is_rejected(
    approval_id,
):
    with pytest.raises(
        TeamsApprovalActionError,
    ):
        parse_teams_approval_action(
            create_activity(
                approval_id=(
                    approval_id
                )
            )
        )


def test_operator_identity_in_activity_does_not_enter_channel_action():
    activity = (
        create_activity()
    )

    action = (
        parse_teams_approval_action(
            activity
        )
    )

    payload = (
        action.model_dump(
            mode="json"
        )
    )

    assert payload == {
        "approval_id": (
            APPROVAL_ID
        ),

        "decision": (
            "approve"
        ),
    }

    assert (
        "aad_object_id"
        not in payload
    )

    assert (
        "tenant_id"
        not in payload
    )

    assert (
        "teams_user_id"
        not in payload
    )

    assert (
        "conversation_id"
        not in payload
    )