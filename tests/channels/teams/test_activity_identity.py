import pytest

from microsoft_teams.api import (
    AdaptiveCardInvokeActivity,
)

from src.channels.teams.activity_identity import (
    TeamsActivityIdentityError,
    extract_teams_operator_identity,
)


TENANT_ID = (
    "0cb40b2b-6cfc-4c63-"
    "bf7b-da710ea390cb"
)

AAD_OBJECT_ID = (
    "11111111-1111-4111-"
    "8111-111111111111"
)

TEAMS_USER_ID = (
    "29:teams-user-001"
)

CONVERSATION_ID = (
    "19:conversation-001@thread.v2"
)


def create_activity(
    *,
    channel_id: str = "msteams",
    aad_object_id: str | None = AAD_OBJECT_ID,
    sender_type: str | None = "person",
    tenant_id: str | None = TENANT_ID,
    conversation_id: str = CONVERSATION_ID,
    action_data: dict | None = None,
) -> AdaptiveCardInvokeActivity:
    if action_data is None:
        action_data = {
            "action": (
                "approval_decision"
            ),

            "approval_id": (
                "apr-11111111-1111-4111-"
                "8111-111111111111"
            ),

            "decision": (
                "approve"
            ),
        }

    channel_data = {}

    if tenant_id is not None:
        channel_data = {
            "tenant": {
                "id": (
                    tenant_id
                ),
            },
        }

    return (
        AdaptiveCardInvokeActivity
        .model_validate(
            {
                "channelId": (
                    channel_id
                ),

                "from": {
                    "id": (
                        TEAMS_USER_ID
                    ),

                    "aadObjectId": (
                        aad_object_id
                    ),

                    "type": (
                        sender_type
                    ),

                    "name": (
                        "Operador Sandbox"
                    ),
                },

                "conversation": {
                    "id": (
                        conversation_id
                    ),
                },

                "channelData": (
                    channel_data
                ),

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
                    "adaptiveCard/action"
                ),

                "value": {
                    "action": {
                        "type": (
                            "Action.Execute"
                        ),

                        "data": (
                            action_data
                        ),
                    },
                },
            }
        )
    )


def test_real_sdk_activity_extracts_operator_identity():
    activity = (
        create_activity()
    )

    identity = (
        extract_teams_operator_identity(
            activity
        )
    )

    assert (
        identity.tenant_id
        == TENANT_ID
    )

    assert (
        identity.aad_object_id
        == AAD_OBJECT_ID
    )

    assert (
        identity.teams_user_id
        == TEAMS_USER_ID
    )

    assert (
        identity.conversation_id
        == CONVERSATION_ID
    )

    assert (
        identity.display_name
        == "Operador Sandbox"
    )


def test_action_data_cannot_replace_authenticated_identity():
    activity = (
        create_activity(
            action_data={
                "action": (
                    "approval_decision"
                ),

                "approval_id": (
                    "apr-test"
                ),

                "decision": (
                    "approve"
                ),

                # Datos controlados por atacante.
                "tenant_id": (
                    "attacker-tenant"
                ),

                "aad_object_id": (
                    "attacker-user"
                ),

                "teams_user_id": (
                    "attacker-teams-user"
                ),

                "conversation_id": (
                    "attacker-conversation"
                ),

                "display_name": (
                    "Attacker"
                ),
            }
        )
    )

    identity = (
        extract_teams_operator_identity(
            activity
        )
    )

    # Siempre prevalece la Activity autenticada.
    assert (
        identity.tenant_id
        == TENANT_ID
    )

    assert (
        identity.aad_object_id
        == AAD_OBJECT_ID
    )

    assert (
        identity.teams_user_id
        == TEAMS_USER_ID
    )

    assert (
        identity.conversation_id
        == CONVERSATION_ID
    )


def test_missing_aad_object_id_fails_closed():
    activity = (
        create_activity(
            aad_object_id=None
        )
    )

    with pytest.raises(
        TeamsActivityIdentityError,
        match="aad_object_id",
    ):
        extract_teams_operator_identity(
            activity
        )


def test_non_human_sender_fails_closed():
    activity = (
        create_activity(
            sender_type="bot"
        )
    )

    with pytest.raises(
        TeamsActivityIdentityError,
        match="identidad humana",
    ):
        extract_teams_operator_identity(
            activity
        )


def test_missing_tenant_fails_closed():
    activity = (
        create_activity(
            tenant_id=None
        )
    )

    with pytest.raises(
        TeamsActivityIdentityError,
        match="tenant_id",
    ):
        extract_teams_operator_identity(
            activity
        )


def test_non_teams_channel_fails_closed():
    activity = (
        create_activity(
            channel_id="webchat"
        )
    )

    with pytest.raises(
        TeamsActivityIdentityError,
        match="msteams",
    ):
        extract_teams_operator_identity(
            activity
        )