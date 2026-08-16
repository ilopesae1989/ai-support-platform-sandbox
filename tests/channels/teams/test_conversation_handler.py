from __future__ import annotations

from pathlib import Path

import pytest

from microsoft_teams.api import (
    MessageActivity,
)

from src.channels.teams.conversation_binding_store import (
    SqliteTeamsConversationBindingStore,
    TeamsConversationBindingNotFoundError,
)

from src.channels.teams.conversation_handler import (
    TeamsConversationHandlerDependencies,
    handle_teams_conversation_message,
    register_teams_conversation_handler,
)


TENANT_ID = (
    "0cb40b2b-6cfc-4c63-bf7b-da710ea390cb"
)

OTHER_TENANT_ID = (
    "11111111-2222-3333-4444-555555555555"
)

CONVERSATION_ID = (
    "19:test-conversation@thread.v2"
)

SERVICE_URL = (
    "https://smba.trafficmanager.net/emea/"
)


def _activity(
    *,
    tenant_id: str = TENANT_ID,
    channel_id: str = "msteams",
    conversation_id: str = CONVERSATION_ID,
    service_url: str = SERVICE_URL,
    text: str = "ping-18.2.15",
) -> MessageActivity:
    return MessageActivity.model_validate(
        {
            "type": "message",
            "id": "activity-001",
            "serviceUrl": service_url,
            "channelId": channel_id,
            "from": {
                "id": "29:test-user",
                "aadObjectId": (
                    "497a925f-15f1-4583-9d15-29b65590bbcf"
                ),
                "name": "Operator",
                "type": "person",
            },
            "conversation": {
                "id": conversation_id,
            },
            "recipient": {
                "id": "28:test-bot",
                "type": "bot",
            },
            "channelData": {
                "tenant": {
                    "id": tenant_id,
                },
            },
            "text": text,
        }
    )


class FakeActivityContext:
    def __init__(
        self,
        activity: MessageActivity,
    ) -> None:
        self.activity = activity
        self.sent: list[str] = []

    async def send(
        self,
        message: str,
    ) -> None:
        self.sent.append(
            message
        )


class FakeApp:
    def __init__(
        self,
    ) -> None:
        self.message_handler = None

    def on_message(
        self,
        handler,
    ):
        self.message_handler = handler
        return handler


def _dependencies(
    database_path: Path,
) -> TeamsConversationHandlerDependencies:
    return TeamsConversationHandlerDependencies(
        expected_tenant_id=TENANT_ID,
        store=(
            SqliteTeamsConversationBindingStore(
                database_path
            )
        ),
    )


@pytest.mark.asyncio
async def test_valid_message_persists_binding_and_acknowledges(
    tmp_path,
):
    dependencies = _dependencies(
        tmp_path / "bindings.db"
    )

    ctx = FakeActivityContext(
        _activity()
    )

    await handle_teams_conversation_message(
        ctx=ctx,
        dependencies=dependencies,
    )

    binding = (
        dependencies.store.get_exact(
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
        )
    )

    assert binding.tenant_id == TENANT_ID
    assert binding.conversation_id == CONVERSATION_ID
    assert binding.service_url == SERVICE_URL

    assert ctx.sent == [
        (
            "AI Support Platform: "
            "conversación Teams registrada."
        )
    ]


@pytest.mark.asyncio
async def test_message_text_never_changes_transport_binding(
    tmp_path,
):
    dependencies = _dependencies(
        tmp_path / "bindings.db"
    )

    ctx = FakeActivityContext(
        _activity(
            text=(
                "azure.vm.delete "
                "target_resource=/tampered "
                "tenant=attacker"
            )
        )
    )

    await handle_teams_conversation_message(
        ctx=ctx,
        dependencies=dependencies,
    )

    binding = (
        dependencies.store.get_exact(
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
        )
    )

    assert binding.tenant_id == TENANT_ID
    assert binding.conversation_id == CONVERSATION_ID
    assert binding.service_url == SERVICE_URL


@pytest.mark.asyncio
async def test_other_tenant_fails_closed_without_persisting(
    tmp_path,
):
    dependencies = _dependencies(
        tmp_path / "bindings.db"
    )

    ctx = FakeActivityContext(
        _activity(
            tenant_id=OTHER_TENANT_ID
        )
    )

    await handle_teams_conversation_message(
        ctx=ctx,
        dependencies=dependencies,
    )

    assert ctx.sent == []

    with pytest.raises(
        TeamsConversationBindingNotFoundError
    ):
        dependencies.store.get_exact(
            tenant_id=OTHER_TENANT_ID,
            conversation_id=CONVERSATION_ID,
        )


@pytest.mark.asyncio
async def test_non_teams_activity_fails_closed_without_persisting(
    tmp_path,
):
    dependencies = _dependencies(
        tmp_path / "bindings.db"
    )

    ctx = FakeActivityContext(
        _activity(
            channel_id="webchat"
        )
    )

    await handle_teams_conversation_message(
        ctx=ctx,
        dependencies=dependencies,
    )

    assert ctx.sent == []

    with pytest.raises(
        TeamsConversationBindingNotFoundError
    ):
        dependencies.store.get_exact(
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
        )


@pytest.mark.asyncio
async def test_registers_real_on_message_boundary(
    tmp_path,
):
    dependencies = _dependencies(
        tmp_path / "bindings.db"
    )

    app = FakeApp()

    registered = (
        register_teams_conversation_handler(
            app=app,
            dependencies=dependencies,
        )
    )

    assert registered is app.message_handler

    ctx = FakeActivityContext(
        _activity()
    )

    await app.message_handler(
        ctx
    )

    loaded = (
        dependencies.store.get_exact(
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
        )
    )

    assert (
        loaded.conversation_id
        == CONVERSATION_ID
    )


def test_dependencies_require_exact_tenant(
    tmp_path,
):
    store = (
        SqliteTeamsConversationBindingStore(
            tmp_path / "bindings.db"
        )
    )

    with pytest.raises(
        ValueError
    ):
        TeamsConversationHandlerDependencies(
            expected_tenant_id=" ",
            store=store,
        )
