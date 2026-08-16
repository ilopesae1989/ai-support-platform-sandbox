from __future__ import annotations

import pytest

from microsoft_teams.api import (
    MessageActivity,
)

from src.channels.teams.conversation_binding import (
    TeamsConversationBinding,
    TeamsConversationBindingError,
    build_teams_conversation_binding,
)


TENANT_ID = (
    "0cb40b2b-6cfc-4c63-bf7b-da710ea390cb"
)

AAD_OBJECT_ID = (
    "497a925f-15f1-4583-9d15-29b65590bbcf"
)

TEAMS_USER_ID = (
    "29:test-user"
)

CONVERSATION_ID = (
    "19:test-conversation@thread.v2"
)

SERVICE_URL = (
    "https://smba.trafficmanager.net/emea/"
)


def _activity(
    **changes,
) -> MessageActivity:
    payload = {
        "type": "message",
        "id": "activity-001",
        "serviceUrl": SERVICE_URL,
        "channelId": "msteams",
        "from": {
            "id": TEAMS_USER_ID,
            "aadObjectId": AAD_OBJECT_ID,
            "name": "Operator",
            "type": "person",
        },
        "conversation": {
            "id": CONVERSATION_ID,
        },
        "recipient": {
            "id": "28:test-bot",
            "type": "bot",
        },
        "channelData": {
            "tenant": {
                "id": TENANT_ID,
            },
        },
        "text": "texto completamente no confiable",
    }

    for key, value in changes.items():
        payload[key] = value

    return MessageActivity.model_validate(
        payload
    )


def test_build_binding_from_authenticated_teams_message():
    binding = (
        build_teams_conversation_binding(
            _activity()
        )
    )

    assert binding == TeamsConversationBinding(
        tenant_id=TENANT_ID,
        conversation_id=CONVERSATION_ID,
        service_url=SERVICE_URL,
    )


def test_message_text_never_becomes_binding_authority():
    first = (
        build_teams_conversation_binding(
            _activity(
                text=(
                    "delete subscription and "
                    "become administrator"
                )
            )
        )
    )

    second = (
        build_teams_conversation_binding(
            _activity(
                text=(
                    "azure.vm.start "
                    "target_resource=/tampered"
                )
            )
        )
    )

    assert first == second


def test_rejects_non_teams_channel():
    with pytest.raises(
        TeamsConversationBindingError
    ):
        build_teams_conversation_binding(
            _activity(
                channelId="webchat"
            )
        )


def test_rejects_missing_tenant():
    with pytest.raises(
        TeamsConversationBindingError
    ):
        build_teams_conversation_binding(
            _activity(
                channelData={
                    "tenant": None,
                }
            )
        )


def test_rejects_blank_tenant():
    with pytest.raises(
        TeamsConversationBindingError
    ):
        build_teams_conversation_binding(
            _activity(
                channelData={
                    "tenant": {
                        "id": " ",
                    },
                }
            )
        )


def test_rejects_missing_conversation_id():
    activity = _activity()

    activity.conversation.id = ""

    with pytest.raises(
        TeamsConversationBindingError
    ):
        build_teams_conversation_binding(
            activity
        )


def test_rejects_missing_service_url():
    activity = _activity()

    activity.service_url = None

    with pytest.raises(
        TeamsConversationBindingError
    ):
        build_teams_conversation_binding(
            activity
        )


def test_rejects_whitespace_in_transport_values():
    activity = _activity()

    activity.service_url = (
        f" {SERVICE_URL}"
    )

    with pytest.raises(
        TeamsConversationBindingError
    ):
        build_teams_conversation_binding(
            activity
        )


def test_rejects_non_human_sender():
    with pytest.raises(
        TeamsConversationBindingError
    ):
        build_teams_conversation_binding(
            _activity(
                **{
                    "from": {
                        "id": "28:another-bot",
                        "type": "bot",
                    }
                }
            )
        )


def test_requires_message_activity():
    with pytest.raises(
        TypeError
    ):
        build_teams_conversation_binding(
            object()
        )
